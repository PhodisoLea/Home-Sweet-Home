# Home Help

A Django marketplace for South African household jobs. Employers can post jobs and manage applications; helpers can create profiles, find jobs and apply. Both sides can message one another and exchange reviews after a job is marked complete.

## Run on Windows

To use the local address **http://homehelp.local:8000/**, add a hosts-file entry once. Open PowerShell as Administrator and run:

```powershell
Add-Content -Path "$env:SystemRoot\System32\drivers\etc\hosts" -Value "`n127.0.0.1 homehelp.local"
```

This address is only available on this computer; it is not a public website. The default Django allowed-host list includes `homehelp.local`; if you set `DJANGO_ALLOWED_HOSTS` yourself, include it there too.

Open this project folder in VS Code. In the VS Code terminal (PowerShell), run:

```powershell
py -3.15 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Then open **http://homehelp.local:8000/**. If Python 3.15 isn't installed, use an installed Python version supported by the pinned Django 6.1 release:

```powershell
py -0p
py -3.14 -m venv .venv
```

Replace `3.14` with an installed Python version supported by Django 6.1 (Python 3.12 or newer). You can also use `python` instead of `py -3.15` when Python is on PATH.

Register at `/accounts/signup/`, choose **Employer** or **Helper**, and complete your profile. At `/accounts/login/`, select the same account type and log in with your username and password. The selected role is checked against the registered account. To stop the development server, press **Ctrl+C** in its terminal.

If you forget your password, use **Forgot password?** on the login page. In local development, Django prints the password-reset email and one-time link in the server terminal. In production, configure the `DJANGO_EMAIL_*` environment variables shown in `.env.example` in your hosting environment; `.env.example` is a reference template and is not loaded automatically. Passwords can be revealed temporarily with the **Show** button beside password fields.

## What's included

- Django 6.1, SQLite, built-in hashed-password authentication and role-specific registration.
- One-time password reset links and accessible show/hide password controls.
- Employer job posting and application management; helper profiles, job search and applications.
- Helpers can self-report availability; employers can browse available profiles, and urgent job posts are highlighted.
- Job posts include an optional calendar-based start date alongside the schedule text for hours and recurring days.
- Private, participant-only job conversations and a Home Help assistant with in-app guidance and direct page links.
- Mutual reviews enabled after an employer marks the work complete.
- Django admin at `/admin/`; create its first account with `python manage.py createsuperuser`.
- Database migrations and workflow tests (`python manage.py test marketplace`).

The local SQLite database is `db.sqlite3`, created by the migrations. Its data persists between server restarts. The database is excluded from version control.

## Where to change things

| Change | File |
| --- | --- |
| Page layout, navigation and template links | [base.html](./marketplace/templates/marketplace/base.html) |
| Page content: dashboard, jobs, applications, messages and reviews | [marketplace/templates/marketplace/](./marketplace/templates/marketplace/) |
| Appearance, responsive layout and Home Help styling | [styles.css](./static/styles.css), [moya.css](./static/moya.css) |
| Database models and job/application status choices | [models.py](./marketplace/models.py) |
| Signup, job, application, profile and review forms | [forms.py](./marketplace/forms.py) |
| Page actions, permissions, messaging and guide replies | [views.py](./marketplace/views.py) |
| Page URLs | [urls.py](./marketplace/urls.py) |
| Project configuration, database and security settings | [settings.py](./moya_home/settings.py) |
| Tests for roles, privacy, applications and messaging | [tests.py](./marketplace/tests.py) |

After changing a model, run `python manage.py makemigrations` and `python manage.py migrate`. After changing a page or workflow, run `python manage.py test marketplace`.

## Important security and production notes

This starter **does not** collect or verify South African ID numbers or passport documents. Every profile is labelled unverified. Do not add ID/passport-number fields until you have an authorised verification provider, informed consent, a privacy and retention policy, secure document handling, and appropriate legal review.

The Home Help assistant uses rule-based in-app guidance; it is not a generative AI model, live internet search, live support service, or professional advice. It can answer common product and household-work questions and link to relevant pages. Unsupported topics are labelled **Not found in Home Help** rather than answered as verified facts. Search history is kept in the current browser tab only and can be cleared from the assistant page. Messages and profiles are stored in the local SQLite database without production-grade operational monitoring or backups. Before deployment, set a unique `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, and `DJANGO_ALLOWED_HOSTS` using environment variables; configure HTTPS at your hosting provider or reverse proxy; and set up a production database, email, backups and security monitoring. The production settings redirect HTTP to HTTPS and enable HSTS. The default secret is for local development only. Do not expose Django's development server to the public internet.
