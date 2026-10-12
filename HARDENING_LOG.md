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
