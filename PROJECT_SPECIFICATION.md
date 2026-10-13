# SJCRM Project Specification

## About the project

**SJCRM** stands for **Smart Journey Customer Relationship Management**. It is a web-based customer relationship management system for organizing customer information and coordinating sales, support, tasks, and campaigns in one workspace.

The application is designed for teams. Administrators manage access and workspace settings, managers oversee their teams, and staff work with records assigned to them or shared with their team.

## Project goals

- Keep customer and company information organized.
- Track leads and sales opportunities from first contact through completion.
- Coordinate customer support, follow-up tasks, and campaigns.
- Give each team member access appropriate to their role and team.
- Provide a responsive interface for desktop and mobile screens.

## Features

### Customer and sales management

- **Leads:** Store name, work email, phone, company, source, status, owner, team, and remarks. Lead remarks accept up to 2,000 characters.
- **Contacts:** Store contact details and link contacts to companies.
- **Companies:** Store company name, website, industry, phone, owner, and team.
- **Deals:** Link deals to companies and contacts, track sales stages and expected close dates, and record amounts displayed in Indian rupees (INR).
- **Support cases:** Track case status, priority, description, and related contact.
- **Tasks:** Track task status, due date, details, and related contact, deal, or support case.
- **Campaigns:** Track channel, status, budget, dates, goal, target contacts, responses, conversions, revenue, and linked contacts.

### Workspace tools

- Dashboard with counts for open leads, active deals, open support cases, and tasks to do.
- Reports for sales pipeline, campaigns, and task/deal totals.
- Search, status filtering, record creation and editing, and CSV export.
- Team and user management for administrators.
- Audit history for important account and record actions.
- Downloadable ZIP backup containing CSV files for CRM records, teams, users, campaign-contact links, and audit history. Passwords, sessions, OAuth tokens, and deployment secrets are excluded. This export is not a complete database restore.

### Accounts and sign-in

- Accounts are invite-only; a workspace administrator creates accounts.
- Sign in with a work email and password.
- Google sign-in is available when OAuth is configured.
- Password setup and reset email delivery depend on the configured email provider.
- Repeated unsuccessful login attempts trigger a temporary lockout.

## User roles and access

| Role | Access |
| --- | --- |
| Administrator | Manage workspace members and teams; access CRM records and settings; view workspace audit history. |
| Manager | Work with records in their team and review their team's audit history. |
| Staff | View team-shared and personally assigned records; edit and delete records assigned to them. |
| Django superuser | Access `/admin/` and Django's administrative tools. The CRM Administrator role alone does not grant Django admin access. |

Record access is enforced by the Django application. Supabase Row Level Security is not used by the application's Django database connection.

## Main pages

- Sign in and password reset
- Dashboard
- Leads, contacts, companies, and deals
- Support cases, tasks, and campaigns
- Reports and search
- Settings, team members, and teams
- Audit history
- Django administration at `/admin/` for active superusers

## Technology and architecture

- **Backend:** Python and Django 5.2.
- **Frontend:** Django templates, HTML, and project CSS.
- **Authentication:** Django authentication, django-allauth, optional Google OAuth, and django-axes login protection.
- **Local database:** SQLite when running locally with `DEBUG` enabled and no `DATABASE_URL`.
- **Production database:** PostgreSQL on Supabase, configured with `DATABASE_URL` and the transaction pooler.
- **Hosting:** Vercel runs the Django WSGI application and collects static assets during deployment.
- **Currency display:** Monetary values are formatted in INR (₹).

## Security and reliability

- Production requires `DJANGO_SECRET_KEY` and `DATABASE_URL`.
- Production settings enable HTTPS redirects, secure session and CSRF cookies, HSTS, and security headers.
- Passwords use Argon2 hashing and Django password validators.
- Public account registration is disabled.
- Role and team checks protect CRM records and administrator pages.
- Generic 404 and 500 pages avoid showing internal exception details.
- Database connections use SSL and short-lived connections suited to serverless hosting.
- Back up the production database before schema changes. Run migrations manually against the intended database; Vercel builds must not run migrations.
- Keep downloaded backup files private. Use Supabase database backups for full recovery.

## Deployment configuration

Configure these values in the Vercel project environment, as needed:

- Required: `DJANGO_SECRET_KEY`, `DATABASE_URL`, and valid `ALLOWED_HOSTS`.
- CSRF protection: `CSRF_TRUSTED_ORIGINS` for the deployed HTTPS origins.
- Optional Google sign-in: `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`, plus the correct callback URL in Google Cloud.
- Email delivery: `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, and `DEFAULT_FROM_EMAIL`.

Use separate databases for Preview and Production where possible. Never commit `.env` files or put server credentials in frontend code.

## Scope notes

- The downloadable ZIP is a convenient export of selected workspace data, not a replacement for a full PostgreSQL backup or restore process.
- Google OAuth, production email delivery, database backups, and live deployment settings depend on external provider configuration.
- The application does not include a public API or a new invitation-token workflow; administrators create accounts from workspace settings.
