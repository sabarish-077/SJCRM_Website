# Manual security tasks

These tasks need access to deployment or database controls that are not in this source folder. Do them only in the named service; never paste secret values into this file.

## Secret rotation and repository controls

- [ ] Review GitHub secret-scanning results and access logs. If any live credential was ever committed, exposed in an issue, or shown in a deployment log, rotate it with its provider and update Vercel Production/Preview variables. Never record the value here.
- [ ] Rotation inventory (values intentionally masked/not read): `DJANGO_SECRET_KEY` (invalidate app sessions when rotated), `DATABASE_URL` (Supabase database username/password), `GOOGLE_OAUTH_CLIENT_SECRET`, and `EMAIL_HOST_PASSWORD`. Rotate only the credentials confirmed as exposed, then update the matching Vercel environment and redeploy.
- [ ] Confirm branch protection requires review and passing CI for `main`.

## Hosting and database

- [ ] In Vercel, verify production-only values for `DJANGO_SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS`, and `CSRF_TRUSTED_ORIGINS`; keep Preview on a separate database.
- [ ] In Supabase, confirm the Django connection role is not a superuser and does not bypass row-level security; use the database privilege/RLS queries in `SECURITY_AUDIT.md` as a read-only inspection.
- [ ] Confirm backups/PITR and complete a restore drill in a separate project. Never test restore on production.
- [ ] Review SMTP sender authentication, Google OAuth callback/allowed origins, provider-side rate limits, and live response headers.
- [ ] Check deployed HTTPS responses and cookies on the real Vercel/custom domain: redirect, HSTS, CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, Secure/HttpOnly/SameSite cookie flags.
- [ ] If file uploads are added in future, require an extension and MIME allowlist, a strict byte limit, generated storage names, malware scanning where appropriate, and non-executable private storage before release.
- [ ] Verify the intended production operators have Django `is_superuser` access for `/admin/`; a CRM role named `admin` alone no longer grants Django Admin access.
- [ ] Configure a shared per-IP and per-account/email request limit for `/password-reset/` at Vercel or the mail provider; keep its response generic. Confirm the limit works across serverless instances.
- [ ] In Supabase SQL Editor, inspect the Django connection role (read-only query):

  ```sql
  SELECT current_user, r.rolsuper, r.rolbypassrls
  FROM pg_roles AS r
  WHERE r.rolname = current_user;
  ```

- [ ] Inspect RLS flags on application tables (read-only query):

  ```sql
  SELECT n.nspname AS schema_name, c.relname AS table_name,
         c.relrowsecurity AS rls_enabled,
         c.relforcerowsecurity AS rls_forced
  FROM pg_class AS c
  JOIN pg_namespace AS n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
  ORDER BY c.relname;
  ```

- [ ] Ask the database owner to review the Django role's table grants and remove privileges it does not need. Do not enable RLS on Django tables until compatible policies and the connection role have been designed and tested; this app currently enforces row scope in Django.
