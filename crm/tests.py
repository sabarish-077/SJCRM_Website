import csv
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import get_hasher
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase, override_settings
from orbit_crm.settings import database_config
from django.urls import reverse

from .forms import form_for
from .models import AuditEvent, Company, Contact, Deal, Lead, Team
from .views import server_error


class CRMSmokeTests(TestCase):
    credential = "A-strong-test-password-42!"

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.team_a = Team.objects.create(name="Smoke Team A")
        cls.team_b = Team.objects.create(name="Smoke Team B")
        cls.user_a = user_model.objects.create_user(
            username="smoke-a", email="smoke-a@example.test", password=cls.credential,
            role="staff", team=cls.team_a,
        )
        cls.user_b = user_model.objects.create_user(
            username="smoke-b", email="smoke-b@example.test", password=cls.credential,
            role="staff", team=cls.team_b,
        )
        cls.company_b = Company.objects.create(name="Private Company B", owner=cls.user_b, team=cls.team_b)
        cls.lead_b = Lead.objects.create(name="Private Lead B", owner=cls.user_b, team=cls.team_b)
        cls.contact_b = Contact.objects.create(
            name="Private Contact B", owner=cls.user_b, team=cls.team_b, company=cls.company_b,
        )
        cls.deal_b = Deal.objects.create(
            title="Private Deal B", owner=cls.user_b, team=cls.team_b,
            company=cls.company_b, contact=cls.contact_b,
        )

    def test_login_with_email_succeeds(self):
        response = self.client.post(
            reverse("login"), {"username": self.user_a.email, "password": self.credential}
        )
        self.assertRedirects(response, reverse("dashboard"))

    def test_anonymous_users_are_redirected_from_crm_and_admin(self):
        for url in ("dashboard", "record_list", "admin:index"):
            with self.subTest(url=url):
                kwargs = {"module": "leads"} if url == "record_list" else {}
                response = self.client.get(reverse(url, kwargs=kwargs))
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login/" if url != "admin:index" else "/admin/login/", response["Location"])

    def test_user_cannot_read_or_edit_another_teams_records(self):
        self.client.force_login(self.user_a)
        records = (
            ("leads", self.lead_b, "Private Lead B"),
            ("contacts", self.contact_b, "Private Contact B"),
            ("deals", self.deal_b, "Private Deal B"),
        )
        for module, record, private_name in records:
            with self.subTest(module=module):
                listing = self.client.get(reverse("record_list", kwargs={"module": module}))
                self.assertEqual(listing.status_code, 200)
                self.assertNotContains(listing, private_name)
                edit_url = reverse("record_edit", kwargs={"module": module, "pk": record.pk})
                self.assertEqual(self.client.get(edit_url).status_code, 404)
                self.assertEqual(self.client.post(edit_url, {}).status_code, 404)

    def test_signup_route_does_not_create_an_account(self):
        user_model = get_user_model()
        before = user_model.objects.count()
        response = self.client.post(
            "/accounts/signup/",
            {"email": "attacker@example.test", "password1": self.credential, "password2": self.credential},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "invite-only")
        self.assertEqual(user_model.objects.count(), before)

    def test_csv_export_streams_audits_and_neutralizes_formula_cells(self):
        Lead.objects.create(
            name="  =HYPERLINK(\"https://bad.invalid\")", owner=self.user_a, team=self.team_a,
        )
        self.client.force_login(self.user_a)
        response = self.client.get(reverse("record_export", kwargs={"module": "leads"}))

        self.assertTrue(response.streaming)
        csv_text = b"".join(response.streaming_content).decode("utf-8")
        rows = list(csv.reader(StringIO(csv_text)))
        self.assertEqual(rows[1][0], "'  =HYPERLINK(\"https://bad.invalid\")")
        self.assertNotIn("Private Lead B", csv_text)
        event = AuditEvent.objects.get(actor=self.user_a, module="leads", action="exported")
        self.assertEqual(event.summary, "Exported leads CSV")

    def test_logged_in_user_can_open_key_crm_pages(self):
        self.client.force_login(self.user_a)
        urls = [
            reverse("dashboard"), reverse("reports"), reverse("my_account"),
            *(reverse("record_list", kwargs={"module": module}) for module in (
                "leads", "contacts", "companies", "deals", "support", "tasks", "campaigns",
            )),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("script-src 'self' 'unsafe-inline'", response["Content-Security-Policy"])


class AccessControlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        unused_credential = "unused-test-value"
        cls.manager = user_model.objects.create_user(
            username="teamless-manager", email="manager@example.test", password=unused_credential, role="manager",
        )
        cls.other_user = user_model.objects.create_user(
            username="manager-other", email="other@example.test", password=unused_credential, role="staff",
        )
        cls.other_team = Team.objects.create(name="Manager Other Team")
        cls.other_user.team = cls.other_team
        cls.other_user.save(update_fields=["team"])

    def test_teamless_manager_form_cannot_assign_another_user_or_team(self):
        form = form_for("leads", self.manager)
        self.assertEqual(list(form.fields["owner"].queryset), [self.manager])
        self.assertFalse(form.fields["team"].queryset.exists())

        submitted = form_for("leads", self.manager, data={
            "name": "Attempted transfer", "owner": str(self.other_user.pk), "team": str(self.other_team.pk),
        })
        self.assertFalse(submitted.is_valid())

    def test_crm_admin_role_without_django_superuser_is_denied_admin(self):
        self.client.force_login(self.other_user)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])


class AuthenticationHardeningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.valid_credential = "Good-password-For-Tests-52!"
        cls.user = get_user_model().objects.create_user(
            username="login-protection", email="login-protection@example.test",
            password=cls.valid_credential,
        )

    @override_settings(AXES_FAILURE_LIMIT=2, AXES_COOLOFF_TIME=0.25)
    def test_repeated_bad_passwords_block_a_later_correct_login(self):
        bad_credential = "wrong-test-value"
        login_data = {"username": self.user.email, "password": bad_credential}
        self.client.post(reverse("login"), login_data)
        self.client.post(reverse("login"), login_data)

        response = self.client.post(reverse("login"), {
            "username": self.user.email, "password": self.valid_credential,
        })
        self.assertNotEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_argon2_and_password_validators_are_active(self):
        self.assertEqual(get_hasher().algorithm, "argon2")
        with self.assertRaises(ValidationError):
            validate_password("weak", self.user)
        validate_password("Strong-and-unique-For-Tests-93!", self.user)


class DatabaseConfigurationTests(TestCase):
    def test_postgres_uses_tls_and_transaction_pooler_safe_options(self):
        config = database_config("postgresql://user:masked@db.example.invalid:6543/app")
        self.assertEqual(config["OPTIONS"]["sslmode"], "require")
        self.assertIsNone(config["OPTIONS"]["prepare_threshold"])
        self.assertEqual(config["CONN_MAX_AGE"], 0)


class ProductionErrorPageTests(TestCase):
    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_unknown_page_uses_generic_404_template(self):
        response = self.client.get("/this-route-does-not-exist/and-more/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page not found", status_code=404)
        self.assertNotContains(response, "Traceback", status_code=404)

    def test_server_error_handler_renders_generic_500(self):
        response = server_error(RequestFactory().get("/"))
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "No technical details are shown here.", status_code=500)
