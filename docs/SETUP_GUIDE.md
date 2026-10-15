# OneSmarter CertiVerify — Complete Multi-Laptop Setup Guide

This guide provides step-by-step instructions for cloning, setting up, and running **OneSmarter-CertiVerify** on a new laptop (Windows, macOS, or Linux).

---

## 📋 System Prerequisites

Ensure the following tools are installed on the laptop before starting:

| Tool | Recommended Version | Download Link / Command |
| :--- | :--- | :--- |
| **Git** | 2.30+ | [git-scm.com](https://git-scm.com/) |
| **Python** | 3.10, 3.11, or 3.12 | [python.org](https://www.python.org/downloads/) *(Ensure **"Add python.exe to PATH"** is checked on Windows)* |
| **Node.js & npm** | Node 18+ or 20+ (LTS) | [nodejs.org](https://nodejs.org/) |
| **PostgreSQL** *(Recommended)* | 14, 15, or 16 | [postgresql.org](https://www.postgresql.org/download/) *(Or use SQLite for zero-config testing)* |

---

## 🚀 Step 1: Clone the GitHub Repository

Open **PowerShell** (Windows) or **Terminal** (macOS/Linux):

```bash
git clone https://github.com/<your-username>/OneSmarter-CertiVerify.git
cd OneSmarter-CertiVerify
```

The repository structure:
```text
OneSmarter-CertiVerify/
├── backend/          # Django REST Framework (Python)
├── frontend/         # React.js + TypeScript + Vite + Tailwind CSS
├── docs/             # Documentation & Architecture Guides
├── README.md         # Project overview
└── .gitignore        # Git ignore rules
```

---

## 🐍 Step 2: Backend Setup (Django REST Framework)

### 2.1 Navigate to Backend
```bash
cd backend
```

### 2.2 Create & Activate Python Virtual Environment

- **On Windows (PowerShell):**
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\activate
  ```
  *(If PowerShell shows an execution policy error, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and try again).*

- **On macOS / Linux:**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

Your prompt will now show `(.venv)`.

### 2.3 Install Python Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

*(This installs Django 5.2, Django REST Framework, SimpleJWT, Pillow, PyPDF, PyPDFium2, PyOTP, QRCode, psycopg2-binary, google-auth, etc.)*

### 2.4 Configure Backend Environment Variables (`.env`)

Copy the example file to `.env`:

- **Windows:**
  ```powershell
  copy .env.example .env
  ```
- **macOS / Linux:**
  ```bash
  cp .env.example .env
  ```

Open `backend/.env` in any editor (e.g., VS Code or Notepad) and configure your database and settings:

#### Database Option A: PostgreSQL (Recommended)
1. Open **pgAdmin** or your PostgreSQL command line (`psql -U postgres`).
2. Create the database:
   ```sql
   CREATE DATABASE certiverify_db;
   ```
3. In `backend/.env`, set:
   ```env
   DJANGO_SECRET_KEY=generate-any-long-random-string-here
   DJANGO_DEBUG=True
   DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost

   DB_NAME=certiverify_db
   DB_USER=postgres
   DB_PASSWORD=YOUR_POSTGRES_PASSWORD
   DB_HOST=127.0.0.1
   DB_PORT=5432
   ```

#### Database Option B: SQLite (Zero-Config Quick Mode)
If your friend does not have PostgreSQL installed yet and wants to run the project instantly without installing PostgreSQL, add this line in `backend/.env`:
```env
DB_ENGINE=sqlite
```
*(Django will automatically create and use a local `db.sqlite3` file).*

#### Email Configuration (SMTP)
The project includes centralized SMTP configuration for email verification OTPs and certificate completion emails:
```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.ionos.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_TIMEOUT=20
EMAIL_HOST_USER=akshay.kumar@onesmarter.com
EMAIL_HOST_PASSWORD=YOUR_SMTP_PASSWORD
DEFAULT_FROM_EMAIL=OneSmarter Support <support@onesmarter.com>
FRONTEND_URL=http://localhost:5173
```
> **Tip for Local Testing without Real Emails:**
> Set `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` in `backend/.env`. All emails (including verification OTPs) will print straight to the backend terminal window!

### 2.5 Run Database Migrations
Apply all schema migrations to create the database tables:
```bash
python manage.py migrate
```

### 2.6 Create an Admin Superuser
Create the initial administrator account:
```bash
python manage.py createsuperuser
```
Follow the prompts to enter:
- **Username** (e.g. `admin`)
- **Email address** (e.g. `admin@onesmarter.com`)
- **Password**

*(This user automatically receives the `ADMIN` role in CertiVerify).*

### 2.7 (Optional) Test Email Connectivity
Verify SMTP settings:
```bash
python manage.py test_smtp
```

### 2.8 Start the Backend Server
```bash
python manage.py runserver 8000
```

Backend will be running at:
- **API Base:** `http://127.0.0.1:8000/api/`
- **Django Admin Panel:** `http://127.0.0.1:8000/admin/`

Leave this terminal running.

---

## ⚛️ Step 3: Frontend Setup (React + Vite)

Open a **new terminal tab or window**.

### 3.1 Navigate to Frontend
```bash
cd OneSmarter-CertiVerify/frontend
```

### 3.2 Install Node Modules
```bash
npm install
```

### 3.3 Configure Frontend Environment Variables (`.env`)

Copy the example file to `.env`:

- **Windows:**
  ```powershell
  copy .env.example .env
  ```
- **macOS / Linux:**
  ```bash
  cp .env.example .env
  ```

Open `frontend/.env` and verify the API URL:
```env
# Base URL of the Django REST API (default Django dev port is 8000)
VITE_API_BASE_URL=http://127.0.0.1:8000/api

# Public HTTPS URL of the deployed frontend for LinkedIn Credential verification (leave blank in dev)
VITE_PUBLIC_FRONTEND_URL=

# Google OAuth 2.0 Client ID (optional, for Google Sign-In)
# VITE_GOOGLE_CLIENT_ID=
```

### 3.4 Start the Frontend Dev Server
```bash
npm run dev
```

The frontend will run at:
- **Website URL:** `http://localhost:5173/`

---

## 🌐 Step 4: Verify the Application

1. Open your browser and navigate to: `http://localhost:5173/`
2. Click **Sign In**:
   - Log in using the superuser account you created in Step 2.6.
   - You will land on the **Admin Dashboard** (`/admin`).
3. Explore Admin features:
   - **Single Certificate:** Issue a certificate with custom recipient name, email, course, dates, and preview.
   - **Upload Custom Template:** Upload any Figma PNG, JPG, or JPEG certificate layout.
   - **Bulk CSV Issuance:** Generate certificates in batches from CSV.
   - **Audit Logs & Security:** View real-time activity and verification history.
4. Test Recipient / Student View:
   - Open an incognito browser window.
   - Register a new account (`/register`).
   - Log in to access the **Recipient Dashboard** (`/dashboard`).
   - If an admin previously issued a certificate to that email, it is automatically claimed and displayed under **My Certificates**.
5. Public Certificate Verification:
   - Visit `http://localhost:5173/verify` and enter any Certificate ID or scan a QR code.

---

## 🛠️ Common Issues & Troubleshooting

### 1. `psycopg2` installation error on Windows
- **Cause:** Missing C++ build tools when compiling psycopg2 from source.
- **Solution:** We use `psycopg2-binary>=2.9.9` in `requirements.txt` which installs pre-compiled wheels. If you still encounter an issue, install with:
  ```powershell
  pip install psycopg2-binary
  ```
  Or switch to SQLite by adding `DB_ENGINE=sqlite` in `backend/.env`.

### 2. Frontend says "Unable to connect to server" or "Network Error"
- **Cause:** The backend server is not running or running on a different port.
- **Solution:** Check that `python manage.py runserver 8000` is running in your backend terminal, and ensure `VITE_API_BASE_URL=http://127.0.0.1:8000/api` is in `frontend/.env`.

### 3. CORS Error in browser console
- **Cause:** Django backend rejected the origin.
- **Solution:** `backend/config/settings.py` is pre-configured with `http://localhost:5173` and `http://127.0.0.1:5173` in `CORS_ALLOWED_ORIGINS`. If your frontend runs on another port (e.g. `5174`), add it to `CORS_ALLOWED_ORIGINS` in `backend/.env`:
  ```env
  CORS_ALLOWED_ORIGINS=http://localhost:5174,http://127.0.0.1:5174
  ```

### 4. Emails failing to send / SMTP timeout
- **Cause:** Incorrect SMTP credentials or port blocked by network firewall.
- **Solution:** For local development and testing, switch to the console backend in `backend/.env`:
  ```env
  EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
  ```
  The verification codes and emails will output directly into the backend terminal.

### 5. Media files (Certificates / Templates) 404
- **Cause:** Media serving disabled or `DEBUG=False`.
- **Solution:** In `backend/.env`, ensure `DJANGO_DEBUG=True`. Django automatically serves uploaded templates and generated PDF/PNG certificates under `/media/` in development.

---

## 📦 Sharing via GitHub Checklist

Before your friend clones the repo, ensure:
1. All changes are committed and pushed:
   ```bash
   git status
   git add .
   git commit -m "Complete setup configuration and documentation"
   git push origin main
   ```
2. Note that sensitive files (`backend/.env`, `frontend/.env`, `.venv/`, `node_modules/`, `backend/media/`) are ignored by `.gitignore` and are not committed to GitHub.
3. Your friend just needs to follow **Step 1 through Step 4** above!
