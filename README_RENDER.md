# BEAUTYFLOW — Render deployment

## 1. Database
Create a PostgreSQL database on Render (or use another managed PostgreSQL provider) and copy its internal/external connection string into the web service environment variable `DATABASE_URL`.

## 2. Environment variables
Set:

- `DJANGO_SECRET_KEY` — a strong random secret (Render can generate it)
- `DJANGO_DEBUG=0`
- `DJANGO_ALLOWED_HOSTS=.onrender.com` (add your custom domain if needed)
- `DATABASE_URL=<your PostgreSQL URL>`
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://<your-service>.onrender.com`

## 3. Build / start
Build command:

`./build.sh`

Start command:

`gunicorn beautyflow.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120`

## 4. Create the first admin
After the first deploy, open Render Shell and run:

`python manage.py createsuperuser`

Then use `/django-admin/` for Django admin.

For a development/demo dataset only, you can run:

`python manage.py seed_demo`

This creates demo accounts with passwords shown by the command. Do not use those demo passwords in production.

## 5. Important production note
SQLite is intentionally not used for production. The application reads `DATABASE_URL` and uses PostgreSQL when it is provided.

User-uploaded media (logos, employee photos, service images) is stored on the local filesystem by default. Render's local filesystem is ephemeral, so for production you should later add persistent object storage (S3-compatible storage or equivalent) for media files.
