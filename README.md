# Orbit CRM

A responsive, invite-only CRM built from the Stitch Orbit CRM screens. Django renders the application and enforces account, team, and role access. Production records use Supabase PostgreSQL. Vercel runs the Django WSGI application and serves collected static assets.

## Local setup on Windows

From this folder, open PowerShell and run the following commands (one at a time):

    py -3.12 -m venv .venv
    ./.venv/Scripts/Activate.ps1
    python -m pip install -r requirements.txt
    Copy-Item .env.example .env

Set a unique local DJANGO_SECRET_KEY in .env. Keep .env private. Then run:

    python manage.py migrate
    python manage.py createsuperuser
    python manage.py runserver

Open http://127.0.0.1:8000/. In local DEBUG mode, the app uses SQLite unless DATABASE_URL is set. Create a superuser first; add a team and invite employees from Settings.

## Supabase and Vercel setup

1. Create a Supabase project and copy its Transaction pooler PostgreSQL connection string from Connect. Use the exact host, username, and port shown by Supabase. Put the connection string in Vercel as DATABASE_URL; do not put a database URL or Supabase secret key in browser code.
2. Set these Vercel environment variables for Production and Preview as appropriate: DJANGO_SECRET_KEY (a newly generated random value), DATABASE_URL, ALLOWED_HOSTS, and CSRF_TRUSTED_ORIGINS. ALLOWED_HOSTS must include the exact Vercel host and any custom domain; trusted origins must include their https:// origins.
3. Optionally configure Google OAuth with GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET. Add the callback URL https://YOUR_DOMAIN/accounts/google/login/callback/ to the Google OAuth client. Users must be provisioned first; self-registration is blocked.
4. Configure EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, EMAIL_USE_TLS, and DEFAULT_FROM_EMAIL to enable password setup and reset emails.
5. Create a Vercel project from this repository and set its Root Directory to outputs/orbit_crm. Django is detected from manage.py; Vercel collects static files during the build.
6. Apply Django migrations to Supabase before opening the live site. Use a trusted local environment with the Supabase connection string and run python manage.py migrate; never place a migration/admin database credential in client-side code or in this repository.
7. Create the first superuser against the same production database from a trusted environment, then provision team and employee accounts. Do not enable public registration.

Supabase's transaction pooler is intended for serverless connections. This project disables persistent Django connections, requires SSL, and disables psycopg prepared statements for compatibility with transaction mode. See the Supabase connection guide at https://supabase.com/docs/guides/database/connecting-to-postgres and Vercel's Django guide at https://vercel.com/docs/frameworks/full-stack/django.

## Application behavior

- Admin can access all CRM records and manage teams and users.
- Manager can access records in their team and review that team's audit events.
- Staff can see team-shared records and their own assigned records; edits and deletes are limited to records they own.
- Core screens: dashboard, leads, contacts, companies, deals, support, tasks, campaigns, reports, settings, and audit history.
- Create, edit, delete, search, filter, and CSV export are available for CRM records. Mutations use Django forms, CSRF protection, and role-scoped querysets.

## Security notes

This includes production-only HTTPS redirect, secure session and CSRF cookies, HSTS, clickjacking and content-type protections, a restrictive content security policy, Argon2 password hashing, password validators, invite-only access, login attempt lockout, and audit events. Secrets are loaded from environment variables and production refuses to start without DJANGO_SECRET_KEY and DATABASE_URL.

No software can be guaranteed fully secure or error-free. Before handling real customer data, configure hosting, email, Google OAuth (if desired), the domain and trusted origins; apply migrations; review permissions against your organization's policy; and verify a live deployment with your own Supabase and Vercel projects. Supabase Row Level Security is not used by this Django ORM connection; access is enforced by the authenticated Django server, and database credentials must remain server-side.
