# SJCRM Security and Production-Readiness Audit

## Assumptions

- This checkout is the Django app intended for deployment on Vercel, with Supabase PostgreSQL, as described in `README.md` and `pyproject.toml`.
- Authentication and authorization are implemented by Django and `django-allauth`; CRM data access uses Django ORM. No DRF API, `supabase-py` client, upload handler, Dockerfile, or separate development/production settings module is present in the tracked repository.
- The code's `role` values (`admin`, `manager`, `staff`) are CRM permissions. Django's `is_staff` and `is_superuser` are separate fields.
- I did not inspect Vercel or Supabase dashboards, production environment variables, live response headers, or production data. Deployment-specific claims below are marked for manual verification.
- The local `.env` exists but is ignored and untracked. Its secret values were not read or included in this report.

**Repository map:** `orbit_crm/settings.py` is the only settings module; `orbit_crm/urls.py` routes requests; `crm/views.py`, `forms.py`, `models.py`, `auth.py`, `security.py`, and `admin.py` contain the app's data/auth/access logic. `templates/` and `static/` contain the UI. `requirements.txt` and `pyproject.toml` declare dependencies and a Vercel build hook. No API/DRF serializers, upload handlers, or separate dev/prod settings were found.

## Summary

| ID | Severity | Title | File | Effort |
|---|---|---|---|---|
| H-01 | High | Public signup contradicts invite-only access | `crm/auth.py` | Small |
| H-02 | High | Vercel build runs database migrations | `pyproject.toml` | Small/Medium |
| M-01 | Medium | Manager without a team can assign records across teams | `crm/forms.py` | Small |
| M-02 | Medium | No MFA for CRM administrators or Django Admin | `orbit_crm/settings.py` | Medium |
| M-03 | Medium | CSV export is unbounded, buffered, and unaudited | `crm/views.py` | Small/Medium |
| M-04 | Medium | Deletion audit entries retain customer names without a retention policy | `crm/views.py` | Medium |
| M-05 | Medium | Password-reset requests have no configured throttling | `orbit_crm/urls.py` | Small/Medium |
| L-01 | Low | CSP permits inline scripts | `crm/security.py` | Small |
| L-02 | Low | Record lists truncate at 250 and relational columns can issue N+1 queries | `crm/views.py` | Small/Medium |
| L-03 | Low | No authorization regression tests are present | Repository | Medium |
| L-04 | Low | Dependency ranges are unlocked and vulnerability scanning could not run | `requirements.txt` | Small |

**Counts:** Critical 0 · High 2 · Medium 5 · Low 4.

## Critical

No critical code-level issue was confirmed in this repository review.

## High

### H-01 — Public signup contradicts invite-only access

**Problem:** Both signup adapters allow account creation. The regular adapter unconditionally returns `True`; the social adapter accepts any non-empty email. The README says self-registration is blocked, and users are meant to be provisioned first. Email verification is required, but that does not make account creation invite-only.

**Risk:** Anyone can create verified CRM accounts. New users default to the `staff` role (`crm/models.py:15`) and can access their own records and records shared with their team. Public signup also permits account and verification-email abuse.

**Affected files:** `crm/auth.py:19-31`, `orbit_crm/settings.py:82-90`, `templates/account/signup.html:22-28`, `templates/account/login.html:88-92`, `README.md:26,30`.

**Exact fix:** Reject public signup in both adapters, and keep account provisioning in the authenticated team-member workflow:

```python
class EmailSignupAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False
```

```python
class EmailSignupSocialAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        return False
```

Also remove or replace the public “Create account” links with an invitation-only message. Verify that invited-account setup still works after changing the adapters.

### H-02 — Vercel build runs database migrations

**Problem:** The Vercel build hook runs `python manage.py migrate --noinput` (`pyproject.toml:15-16`). That makes a build mutate whichever database its build environment's `DATABASE_URL` selects. The README instructs configuring both Production and Preview environments, but their actual values cannot be verified here.

**Risk:** Preview or concurrent builds can change a shared production schema before the corresponding application is deployed. A code rollback does not automatically roll back database schema changes, and incompatible migrations can interrupt the live CRM.

**Affected files:** `pyproject.toml:15-16`, `README.md:24-30`.

**Exact fix:** Remove migration execution from the build hook. Keep the Vercel build limited to build-time work, for example:

```toml
[tool.vercel.scripts]
build = "python manage.py collectstatic --noinput"
```

Run migrations once through a controlled release step after reviewing the migration and confirming the target database. Ensure Preview deployments use a separate database, not production credentials.

## Medium

### M-01 — Manager without a team can assign records across teams

**Problem:** A manager gets owner/team form fields (`crm/forms.py:55-65`). The querysets are restricted only when the manager has a team (`crm/forms.py:22-29`). With no team, the owner queryset remains all active users and the team queryset remains all teams. The model form validates that the selected owner belongs to the selected team (`crm/forms.py:47-52`), so a team-less manager can create or edit an owned record and assign it to another team's member/team.

**Risk:** A misconfigured or deliberately team-less manager can create or transfer CRM records into another team's workspace. The manager may lose visibility after reassignment, but the write crosses the intended tenant boundary.

**Affected files:** `crm/forms.py:22-29,47-65`; record create/update uses this form in `crm/views.py:99-118`.

**Exact fix:** Restrict team-less managers to themselves and no team, or reject manager accounts without a team before allowing record writes. For example:

```python
if user.role == "manager":
    if user.team_id:
        owner_qs = owner_qs.filter(team=user.team)
        team_qs = team_qs.filter(pk=user.team_id)
    else:
        owner_qs = owner_qs.filter(pk=user.pk)
        team_qs = Team.objects.none()
```

Add a regression test proving a team-less manager cannot submit another user's owner ID or another team's team ID.

### M-02 — No MFA for CRM administrators or Django Admin

**Problem:** The repository configures password validators and login lockout but no MFA package, settings, or enforcement flow. Django Admin is mounted at the default `/admin/` path (`orbit_crm/urls.py:7`), and CRM admin permissions grant access to customer and team data (`crm/views.py:167-190`).

**Risk:** A stolen administrator password alone can expose or change customer records, users, and teams.

**Affected files:** `orbit_crm/settings.py:68-110`, `orbit_crm/urls.py:7`, `crm/views.py:167-190`.

**Exact fix:** Add a supported TOTP or WebAuthn MFA flow and require enrollment and a successful second factor for CRM administrators and Django Admin. Test account recovery and lost-device handling; do not treat email verification as MFA.

### M-03 — CSV export is unbounded, buffered, and unaudited

**Problem:** Any authenticated user can call a module's export endpoint. Data is correctly filtered through `scoped()`, and formula-leading characters are prefixed, but every accessible record is written into a normal `HttpResponse` in one request. The export does not create an audit event (`crm/views.py:134-145`).

**Risk:** Large exports can consume server memory and request time. A compromised or rogue account can download CRM data without an application-level export event for investigation.

**Affected files:** `crm/views.py:32-38,134-145`; export routes are in `orbit_crm/urls.py:25-30`.

**Exact fix:** Use `StreamingHttpResponse` with a chunked CSV iterator and record an event without storing exported customer values, for example:

```python
AuditEvent.objects.create(
    actor=request.user,
    module=module,
    action="exported",
    summary=f"Exported {module} CSV",
)
```

Consider a role-based export permission and a maximum export size or asynchronous export job for large workspaces.

### M-04 — Deletion audit entries retain customer names without a retention policy

**Problem:** `audit()` places `str(obj)` in the audit summary (`crm/views.py:37-38`). Lead, contact, and company `__str__` methods return customer names (`crm/models.py:27-59`). Deletion records an event before deleting the record (`crm/views.py:122-131`). No retention or purge policy is present in the repository.

**Risk:** Deleting a customer record does not remove the name from the audit database. Audit events can retain personal data indefinitely, complicating deletion and retention obligations.

**Affected files:** `crm/views.py:37-38,122-131`; `crm/models.py:27-59,133-140`.

**Exact fix:** Store the record type and ID in audit summaries instead of `str(obj)`, then define and implement an approved retention period for audit events. Keep any identity needed for investigations in a separately access-controlled, time-limited field.

### M-05 — Password-reset requests have no configured throttling

**Problem:** The public password-reset route is Django's `PasswordResetView` (`orbit_crm/urls.py:11`). `django-axes` limits authentication failures (`orbit_crm/settings.py:68-77`), but no password-reset or email-send rate limit is configured. The generic success URL is good for reducing account enumeration.

**Risk:** Automated requests can generate repeated reset emails and consume the configured SMTP service, even when the response does not disclose whether an account exists.

**Affected files:** `orbit_crm/urls.py:11`, `orbit_crm/settings.py:68-77,121-127`.

**Exact fix:** Add per-IP and per-account throttling for password reset and signup email sends at the app or hosting edge. Keep responses generic and test that the limit does not reveal account existence.

## Low

### L-01 — CSP permits inline scripts

**Problem:** The Content Security Policy includes `script-src 'self' 'unsafe-inline'` (`crm/security.py:18-23`). The templates use an external script (`templates/crm/base.html:48`); no inline `<script>` tag was found in tracked templates.

**Risk:** If an HTML injection bug is introduced, the policy will allow injected inline JavaScript and provide less XSS protection.

**Affected files:** `crm/security.py:18-23`.

**Exact fix:** Remove `'unsafe-inline'` from `script-src`. If future inline scripts are required, use nonces or hashes rather than restoring the broad allowance. Keep the style policy separate; inline styles are currently permitted.

### L-02 — Record lists truncate at 250 and relational columns can issue N+1 queries

**Problem:** Record lists slice the queryset to the first 250 rows without pagination (`crm/views.py:76-97`). Contacts, deals, and support rows include related columns, but the queryset selects only owner/team (`crm/views.py:80`), so rendering related company/contact values can issue extra queries per row.

**Risk:** Users cannot browse records after the first 250 in the list. Relational tables make unnecessary database round trips as row counts increase.

**Affected files:** `crm/views.py:76-97`, `templates/crm/record_list.html:15-24`, `crm/models.py:35-41,61-71,78-95`.

**Exact fix:** Paginate with Django's `Paginator`, and select each module's displayed relationships:

```python
from django.core.paginator import Paginator

related = {
    "contacts": ("company",),
    "deals": ("company", "contact"),
    "support": ("contact",),
}.get(module, ())
qs = scoped(model.objects.select_related("owner", "team", *related), request.user)
page_obj = Paginator(qs, 50).get_page(request.GET.get("page"))
rows = [{"obj": obj, "edit_url": f"/{module}/{obj.pk}/edit/"} for obj in page_obj]
```

Pass `page_obj` to the template and render previous/next page links.

### L-03 — No authorization regression tests are present

**Problem:** No test modules or test files are tracked in this repository. The role-scoping and object-level checks are implemented in `crm/views.py:32-35,99-145`, but there are no automated regression tests for them.

**Risk:** A later change can silently expose another team's customer records or allow an unauthorized edit/export.

**Affected files:** Repository; authorization code in `crm/views.py:32-35,76-145,158-190` and `crm/forms.py:19-65`.

**Exact fix:** Add Django tests for unauthenticated access, staff access to own/shared/other-team records, manager access with and without a team, admin access, IDOR attempts on edit/delete, and export scoping. Run them in CI on each change.

### L-04 — Dependency ranges are unlocked and vulnerability scanning could not run

**Problem:** Dependencies use version ranges in both `requirements.txt:1-7` and `pyproject.toml:5-12`; no lockfile is tracked. `pip-audit` is not installed. The requested fallback `pip list --outdated` could not reach the package index because DNS/network access failed. This audit therefore did not establish whether any installed package has a published vulnerability.

**Risk:** Separate builds may resolve different transitive dependency versions, and the repository currently has no repeatable dependency vulnerability scan.

**Affected files:** `requirements.txt:1-7`, `pyproject.toml:1-12`.

**Exact fix:** Commit a generated `uv.lock` (or equivalent lock/constraints file) and make the deployment resolve from that lock. Run `pip-audit` in an online CI job and review/upgrade any confirmed advisories; no CVE is asserted by this audit.

## Cannot verify from code

- **Vercel environment:** In the local ignored `.env`, `DJANGO_DEBUG=True`, `DATABASE_URL` is absent, and Django selects SQLite. Verify in Vercel **Project → Settings → Environment Variables** that Production has `DJANGO_DEBUG=false` (or unset), a unique long `DJANGO_SECRET_KEY`, the intended `DATABASE_URL`, and correct `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`. Do not reuse the production database in Preview. These dashboard values were not inspected.
- **Observed Django checks:** `python manage.py check --deploy` could not start using the Windows Store `python` shim. Retried with `.venv\\Scripts\\python.exe`; it ran and reported W004, W008, W012, W016, and W018 because the local `.env` has `DEBUG=True`. A simulated production run with `DEBUG=false`, a deliberately fake short key, and a non-connectivity-tested placeholder PostgreSQL URL reported only W009 for that fake key. The simulated result is not a production verification.
- **Dependency scan:** `pip-audit -r requirements.txt` failed because `pip-audit` is not installed. The `pip list --outdated` fallback failed to resolve the package index host. The local environment includes Django 5.2.18, django-allauth 65.19.7, and django-axes 8.3.1, but no current advisory status is asserted.
- **Secret history:** Searches were run for `SECRET`, `service_role`, `password`, `api_key`, and `token`; `.env` is ignored and not tracked, and history lists `.env.example`, not `.env`. A current-source scan found no hard-coded credential assignment. Review GitHub secret scanning and repository history if any credentials were ever pasted into commits, issues, or deployment logs; rotate any exposed value.
- **Supabase RLS and database role:** The application uses Django ORM via `DATABASE_URL`; README states Supabase RLS is not used by this connection (`README.md:46`). Verify the actual production database role is not a superuser or `BYPASSRLS` role and has only the needed schema/table privileges. In Supabase **SQL Editor**, run:

  ```sql
  SELECT current_user, r.rolsuper, r.rolbypassrls
  FROM pg_roles AS r
  WHERE r.rolname = current_user;
  ```

  Check table RLS flags:

  ```sql
  SELECT n.nspname AS schema_name, c.relname AS table_name,
         c.relrowsecurity AS rls_enabled,
         c.relforcerowsecurity AS rls_forced
  FROM pg_class AS c
  JOIN pg_namespace AS n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
  ORDER BY c.relname;
  ```

  If browser/mobile clients ever access Supabase directly, enable and test RLS policies before exposing any tables. Do not put a `service_role` key in browser code.
- **Backups and recovery:** Check Supabase **Database → Backups** for retention/PITR availability on the selected plan, and perform a restore drill to a separate project. No backup configuration or restore procedure is in this repository.
- **TLS/security headers:** Check the live production and custom-domain responses for HTTPS redirect, HSTS, CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and secure session/CSRF cookies. `settings.py` configures these for `DEBUG=False`, but live headers and proxy behavior are outside the repository.
- **Email and OAuth:** Verify production SMTP delivery, sender SPF/DKIM/DMARC, reset-email limits, and Google OAuth allowed origins/callback URL. Environment values and provider-side settings are not available here.
- **Logging/monitoring/errors:** No project-specific `LOGGING` configuration, custom 404/500 templates, or error-monitoring integration was found. Check Vercel runtime logs/retention and alerting, ensure logs do not contain passwords, reset tokens, or unnecessary customer data, and test that production errors do not expose tracebacks.
- **Storage and uploads:** No upload handlers, media storage, Supabase Storage client, or bucket usage is present. If these are added or enabled outside this code, verify bucket privacy and per-user access policies.
- **Privacy and compliance:** Confirm the data retention/deletion schedule, export approvals, customer data access process, privacy notice, and applicable India DPDP obligations with the operator. Managed database at-rest encryption and data residency cannot be confirmed from code.
- **Hosting and domain:** README and `pyproject.toml` indicate Vercel, but project deployment settings, environment scoping, CDN behavior, custom domain, and actual runtime version are not accessible here. No Dockerfile, Procfile, or CI workflow is tracked.

## Recommended fix order

1. Disable public signup in both adapters and confirm invited accounts still work.
2. Remove database migrations from Vercel builds; apply migrations in a controlled release process, with Preview isolated from production.
3. Restrict team-less manager forms, then add role/IDOR/export regression tests.
4. Add MFA for administrators and throttle password-reset/signup email flows.
5. Stream and audit CSV exports; adopt a retention-safe audit summary format.
6. Lock dependencies, run an online vulnerability scan in CI, and tighten the script CSP.
7. Add proper pagination and module-specific `select_related`, then verify production environment, database role, RLS, backups, email, headers, logs, and restore procedure using the manual checklist above.
