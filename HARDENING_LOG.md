# Security hardening log

This is the plain-language notebook for the hardening work. Each numbered step gets its own commit. “Done” means the code change and the checks described here were completed in this checkout; it does not claim a production dashboard or database was inspected.

## Starting assumptions

- This is the intended SJCRM Django source folder, and the work branch starts from the current `main` plus the already completed H1/H2 commits.
- The project uses Django/allauth and PostgreSQL through `DATABASE_URL`. The local ignored `.env` is not printed or committed.
- Code search found no DRF API, Supabase client, file upload handler, webhook endpoint, or separate production settings module. If one is added later, its checklist item must be revisited.
- We cannot see the Vercel or Supabase dashboards from this source checkout. Those checks stay in `MANUAL_TODO.md`.

## Step 1.5 — Add quick safety tests

**Done.** Added a small Django test suite for email login, anonymous redirects, cross-team lead/contact/deal visibility and edits, invite-only signup, and the main logged-in CRM pages. This is like checking that the front door opens for a teammate and stays locked to strangers.

**Checks:** `manage.py check` passed; all 5 smoke tests passed; `git diff --check` passed.

## Step 3 — Keep records inside the right workspace

**Done.** A manager with no team can now assign records only to themself and cannot choose any team. Django Admin now requires an active Django superuser, which is a stricter gate than the app's separate CRM `admin` role. Added tests for both rules. The existing record views use workspace-scoped querysets for edit/delete and list/search/export; the smoke suite checks cross-team lead, contact, and deal reads/edits. No DRF or other API routes were found, so there was no API permission layer to change.

**Checks:** `manage.py check` passed; all 7 tests passed; `git diff --check` passed.

## Step 4 — Slow down password guessing

**Done.** The app already has django-axes: five failures lock out the username or IP, with a 15-minute cool-off. The installed version was checked: the two separate lockout keys mean either one can trigger the lock. Argon2 is the active password hasher, and Django's similarity, 12-character minimum, common-password, and numeric-only validators are enabled. Added tests proving a valid password is rejected after repeated failures and weak passwords fail validation.

Password-reset email throttling is not currently implemented. A safe shared rate limit should be configured at the hosting/email edge; a per-process counter would reset between serverless requests. This remains in `MANUAL_TODO.md`.

**Checks:** `manage.py check` passed; all 9 tests passed; `git diff --check` passed.

## Step 5 — Protect the database connection

**Done.** The query review found no raw SQL, cursor execution, or hand-built SQL; record queries use Django's ORM. I found that settings asked the URL parser for SSL, then accidentally replaced all of the parsed database options while setting the Supabase pooler option. The code now explicitly keeps `sslmode=require` and `prepare_threshold=None` together, with no persistent connections. A fast unit test checks that configuration without connecting to any database.

The actual Supabase database username, superuser/BYPASSRLS status, grants, and table RLS flags cannot be verified from source. Read-only SQL and a least-privilege review are in `MANUAL_TODO.md`. No production database was contacted or changed; no migration was run.

**Checks:** `manage.py check` passed; all 10 tests passed; `git diff --check` passed.

## Step 6 — Validate data and harden browser responses

**Done.** The app uses Django forms and ORM field validation for CRM inputs; no file-upload or CSV-import route/model exists to expose an upload parser. The CSV export is now streamed in small chunks, filtered by the user's record scope, formula-neutralized even when whitespace comes before a formula, and logged without storing exported customer values. Added a test for streaming, scope, formula safety, and the audit event. No code was added for uploads; if uploads are introduced later, allowlist file types, cap sizes, and store files outside executable/static paths.

The templates use an external JavaScript file and have no inline scripts, so `unsafe-inline` was removed from `script-src`. Existing production-only settings already enable secure session/CSRF cookies, HTTPS redirect, HSTS, `nosniff`, frame denial, and same-origin referrer policy; the live proxy/domain behavior still needs the manual response-header check.

**Checks:** `manage.py check` passed; all 11 tests passed; `git diff --check` passed.

## Step 7 — Keep deployment settings and errors safe

**Done.** `DEBUG` defaults to false and the app refuses to start in production without its secret key and database URL. Hosts come from `ALLOWED_HOSTS` plus Vercel's host variables, and trusted origins come from explicit environment settings. Added generic 404/500 pages that do not reveal exception details. No webhook endpoint, CORS middleware, or cross-origin API exists, so there is nothing to sign or open to browser origins today; future-integration rules are recorded in `MANUAL_TODO.md`.

The live Vercel variables, custom domain, proxy behavior, and error responses still need dashboard/production verification; no production URL was changed or contacted.

**Checks:** `manage.py check` passed; all 13 tests passed; `git diff --check` passed.

## Step 8 — Check dependency advisories

**Attempted, blocked by network.** Installed `pip-audit` in the ignored local virtual environment and attempted both a requirements scan and an installed-environment scan. The first attempt needed a temporary environment; after redirecting its temporary files to the ignored `.venv`, the scanner could not resolve `pypi.org` for vulnerability data. No advisory result was produced. No dependency versions were changed because that would be guessing without a scan result. The ranges remain unlocked, so an online CI/developer run and a lockfile review are still needed.

**Checks:** `manage.py check` passed; all 13 tests passed; `git diff --check` passed. Dependency audit itself remains incomplete until PyPI or OSV is reachable.

## Step 9 — Review the complete hardening diff

**Done.** Reviewed the changes against `main` and ran Bandit across the Django source; it reported no issues. The review found the local-only fallback Django signing key was still a fixed literal. Settings now require `DJANGO_SECRET_KEY` in every environment, matching the README, and tests use named dummy credentials so the static scan can distinguish fixtures from application secrets.

The production-style `check --deploy` ran with disposable fake settings and returned no warnings. It did not connect to the placeholder database, and it does not prove that Vercel/Supabase production settings are correct. The external `pip-audit` scan remains blocked as described in Step 8.

**Checks:** `manage.py check` passed; all 13 tests passed; Bandit reported no issues; production-style `check --deploy` reported no issues; `git diff --check` passed.

## Continuation summary

- Step 1.5 and Steps 2–7: completed in separate commits.
- Step 8: attempted but dependency advisory lookup is incomplete because PyPI DNS is unavailable; follow-up is listed in `MANUAL_TODO.md`.
- Step 9: completed in its own commit.
- Dashboard-only checks, production database role/RLS, provider credentials, domain headers, backups, and restore checks remain manual and are listed in `MANUAL_TODO.md`.

## Step 2 — Scan secrets and environment settings

**Done.** Scanned current source and reachable Git history for common private-key, cloud-token, OAuth-key, and credentialed-database-URL shapes. The scan found no matches; it printed no secret values. `.env` is ignored and untracked; `.env.example` is the only environment file in Git and contains blank secret fields. Existing `.gitignore` rules already cover `.env` and `.env.*` while allowing `.env.example`, so they were left intact.

The application reads its signing key, database URL, allowed hosts, trusted origins, OAuth secret, and email credentials from environment variables. The rotation checklist in `MANUAL_TODO.md` lists the relevant credential names with all values masked. A pattern scan cannot prove that no unknown/custom credential format exists; GitHub secret scanning and provider logs still need a human review.

**Checks:** `manage.py check` passed; all 5 smoke tests passed; `git diff --check` passed.
