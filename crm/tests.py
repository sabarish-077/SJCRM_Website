from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import form_for
from .models import Company, Contact, Deal, Lead, Team


class CRMSmokeTests(TestCase):
    password = "A-strong-test-password-42!"

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.team_a = Team.objects.create(name="Smoke Team A")
        cls.team_b = Team.objects.create(name="Smoke Team B")
        cls.user_a = user_model.objects.create_user(
            username="smoke-a", email="smoke-a@example.test", password=cls.password,
            role="staff", team=cls.team_a,
        )
        cls.user_b = user_model.objects.create_user(
            username="smoke-b", email="smoke-b@example.test", password=cls.password,
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
            reverse("login"), {"username": self.user_a.email, "password": self.password}
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
            {"email": "attacker@example.test", "password1": self.password, "password2": self.password},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "invite-only")
        self.assertEqual(user_model.objects.count(), before)

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
                self.assertEqual(self.client.get(url).status_code, 200)


class AccessControlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.manager = user_model.objects.create_user(
            username="teamless-manager", email="manager@example.test", password="unused", role="manager",
        )
        cls.other_user = user_model.objects.create_user(
            username="manager-other", email="other@example.test", password="unused", role="staff",
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
