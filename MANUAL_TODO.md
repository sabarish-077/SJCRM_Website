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
