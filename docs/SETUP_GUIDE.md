# OneSmarter CertiVerify — Windows Local Setup

This guide configures a fresh, independent development environment after cloning the shared repository. It does not copy another developer's database, media, `.env` files, or credentials.

## Repository layout and local ports

- `backend/`: Django 5.2.18, Django REST Framework, PostgreSQL settings, migrations, uploaded/generated media.
- `frontend/`: React 18, TypeScript, Vite. Use the committed `package-lock.json` with `npm ci`.
- `docs/`: API, schema, and setup documentation.
- Vite runs at `http://localhost:5173` and proxies `/api` to Django at `http://127.0.0.1:8000` by default (`frontend/vite.config.ts`). Run Django on **8000** unless you also update the local `DEV_API_PROXY_TARGET`.
- PostgreSQL is the default database. The backend uses `DB_PORT` when set and defaults to **5432**, PostgreSQL's standard port. If your PostgreSQL service uses a different port, set `DB_PORT` in `backend/.env` to that service's actual port. Django itself runs on port **8000**.

## 1. Install prerequisites

Install Git for Windows, Python 3.12 (64-bit), Node.js 20 LTS (npm included), and PostgreSQL 14–16 (or a compatible newer release). Django 5.2 supports Python 3.10 and later; Python 3.12 is the recommended version for this setup. During Python installation, enable **Add Python to PATH**.

Check versions in PowerShell:

```powershell
git --version
py -3.12 --version
node --version
npm --version
```

If `py -3.12` is unavailable, install Python 3.12, reopen PowerShell, and retry.

## 2. Clone or inspect the existing checkout

For a new clone:

```powershell
git clone https://github.com/kkartik1729/OneSmarter-CertiVerify.git
Set-Location OneSmarter-CertiVerify
```

For an existing clone, open PowerShell in its root and inspect before changing anything:

```powershell
git status --short
git branch --show-current
git remote -v
```

Do not reclone over an existing folder or discard local changes. Open the repository root (the directory containing `backend`, `frontend`, and `docs`) in VS Code with `code .`; in Antigravity, use **Open Folder** and choose that same root.

## 3. Create a local backend environment

In PowerShell from the repository root:

```powershell
Set-Location backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python --version
python -m django --version
```

If PowerShell blocks activation, either run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal and activate again, or skip activation and run `\.venv\Scripts\python.exe -m pip ...` and `\.venv\Scripts\python.exe manage.py ...` explicitly. The virtual environment is local and ignored by Git.

## 4. Configure local backend settings

Create `backend/.env` only if it does not already exist:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

The example is safe for local use and does not contain another developer's credentials. Generate a private Django key in PowerShell with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Paste the generated value into your local `DJANGO_SECRET_KEY`. Set the database values to the database/user/password you create below. The example uses the console email backend, which prints development messages and OTPs in the Django terminal. To use SMTP, replace it with an SMTP backend and credentials issued specifically for development; never copy production credentials.

Relevant variables:

| Variable | Local value / guidance |
| --- | --- |
| `DJANGO_SECRET_KEY` | A fresh random value; keep private. |
| `DJANGO_DEBUG` | `True` for local development only. |
| `DJANGO_ALLOWED_HOSTS` | `127.0.0.1,localhost` for localhost work. |
| `DB_ENGINE` | Leave unset for PostgreSQL; use `sqlite` only for an isolated quick smoke-test database. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD` | The separate local PostgreSQL database and account created below. |
| `DB_HOST`, `DB_PORT` | Usually `127.0.0.1` and `5432`; use the actual local PostgreSQL port. |
| `FRONTEND_URL` | `http://localhost:5173`. |
| `EMAIL_BACKEND` | Console backend locally; SMTP is optional. |
| `GOOGLE_CLIENT_ID` | Optional backend OAuth client ID. Do not put a client secret in frontend config. |
| `CORS_ALLOWED_ORIGINS` | Usually blank; localhost Vite origins are already allowed by Django. |
| `CSRF_TRUSTED_ORIGINS` | Set explicit HTTPS origins only when production CSRF-protected requests require them; local Vite origins are enabled only in development. |

## 5. Create a separate local PostgreSQL database

Check that PostgreSQL is installed and its service is running:

```powershell
Get-Service *postgres*
Test-NetConnection 127.0.0.1 -Port 5432
```

Start the PostgreSQL service from Windows Services or an elevated PowerShell session if it is stopped. The service name includes the installed major version. In pgAdmin or `psql`, connect to the local server and create a dedicated role/database. Replace the example password locally; do not use these literal values as credentials:

```sql
CREATE ROLE certiverify_dev WITH LOGIN PASSWORD 'choose-a-local-password';
CREATE DATABASE certiverify_db OWNER certiverify_dev;
```

If a local database with that name already exists, inspect it and choose another development database name instead of dropping or recreating it. Set `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT` in `backend/.env` to match. Verify a connection before migrations:

```powershell
psql -h 127.0.0.1 -p 5432 -U certiverify_dev -d certiverify_db -c "SELECT current_database();"
```

If `psql` is not on `PATH`, use SQL Shell (psql) installed with PostgreSQL or pgAdmin's Query Tool. Do not import another laptop's database backup or production data as part of this setup.

## 6. Review and apply Django migrations

From `backend/` with the virtual environment active:

```powershell
python manage.py showmigrations
python manage.py migrate --plan
```

Review the plan, then apply the project's migrations to the **new local database**:

```powershell
python manage.py migrate
python manage.py makemigrations --check
python manage.py check
python manage.py test
```

The test suite may use SQLite for convenience. Row-locking behavior such as
`select_for_update()` differs from PostgreSQL on SQLite, so concurrency and
locking behavior should also be validated against a disposable PostgreSQL test
database before relying on it in production.

Local development uses an in-process cache. Production uses Django's shared
PostgreSQL cache backend; after selecting the production environment and
verifying the target database, create its cache table once with
`python manage.py createcachetable`. This adds the cache table and does not
alter certificate or account records. If production is configured to use
Redis instead, provision Redis and use the approved Redis cache configuration
rather than creating the PostgreSQL cache table.

Do not delete migrations, use `--fake`, flush tables, or run destructive SQL to resolve setup issues. The migrations create the schema; this setup does not create an admin account until the next step.

## 7. Create your own admin and handle MFA

```powershell
python manage.py createsuperuser
```

Use your own local username, email, and password. A Django superuser is treated as an admin by this project. Log in through the app and complete authenticator-app MFA enrollment if prompted or required by the account workflow. Do not reuse another person's admin credentials.

## 8. Configure and build the frontend

Open a second PowerShell terminal at the repository root:

```powershell
Set-Location frontend
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
npm ci
npm run build
npm run dev
```

The committed frontend example sets `VITE_API_BASE_URL=/api` and `DEV_API_PROXY_TARGET=http://127.0.0.1:8000`; this keeps requests on the same local Vite origin and matches the Django command below. Do not change API URLs in application source files. If Django runs on another port, edit only `DEV_API_PROXY_TARGET` in local `frontend/.env` and restart Vite.

Optional Google sign-in requires an authorized OAuth web client. Set the same client ID in `frontend/.env` as `VITE_GOOGLE_CLIENT_ID` and in `backend/.env` as `GOOGLE_CLIENT_ID`, and authorize `http://localhost:5173` in that client's development origins. If no authorized client is available, leave it unset; password login remains available.

## 9. Start and smoke-test both servers

In the backend terminal (`backend/`):

```powershell
python manage.py runserver 8000
```

In the frontend terminal (`frontend/`):

```powershell
npm run dev
```

Open `http://localhost:5173`. The Django admin is at `http://127.0.0.1:8000/admin/`; the API is at `http://127.0.0.1:8000/api/`. Verify the app can log in with the newly created account and load its courses/templates. Test certificate generation only with local test data and the console email backend; no real email is sent by that backend. Use a fresh local template upload if the clone has no authorized media files.

## Optional: access from a phone on the same private Wi-Fi

Vite is already configured to bind to `0.0.0.0`. Do not expose these development servers to the public internet. For phone testing, use the laptop's private LAN IPv4 address in the browser. Configure Django `ALLOWED_HOSTS` to include that address and `CORS_ALLOWED_ORIGINS` to include the Vite origin using that address (for example `http://192.168.1.25:5173`); set the local frontend `DEV_API_PROXY_TARGET` to the laptop's LAN address on port 8000. Allow only ports 5173 and 8000 on a trusted private network if Windows Firewall requires it. Return those values to localhost when finished.

## Local-only files and common issues

- Backend `.env`, frontend `.env`, `.venv`, `node_modules`, `dist`, `backend/media`, and database dumps/backups are machine-specific and must stay out of commits. Existing uploads and generated records are not included in a fresh clone; obtain any needed template assets from an authorized source and upload them locally.
- **Repository-owner action before sharing a fresh clone:** the current worktree removes `backend/certiverify_backup.dump` and ignores database dumps, but prior Git history may still contain it. Do not import it into a local database. The repository owner must review approved history cleanup and rotate credentials or sessions that may have been exposed before sharing or publishing the repository. History rewriting and credential rotation are external operations and are not performed by this local setup guide.
- `connection refused` from PostgreSQL: check the service and actual port, then compare them with `DB_HOST`/`DB_PORT`.
- Frontend API network error: keep Django on port 8000 or align local `DEV_API_PROXY_TARGET`; restart Vite after editing `.env`.
- Email/OTP testing: keep the console backend selected so messages and codes appear in the backend terminal. Use SMTP only with separate development credentials and an authorized test recipient.
- Google sign-in unavailable: configure an authorized development client ID and local origin as described above; do not invent or reuse private credentials.

## Repository changes

Setup commands above do not require source changes, Git commits, or pushes. Before sharing any changes, inspect `git status` and ensure no local `.env`, database, media, or backup files are staged.
