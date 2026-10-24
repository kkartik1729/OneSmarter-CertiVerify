# OneSmarter CertiVerify

Certificate issuance and record lookup application built with Django REST Framework and React.

---

## 🌟 Technology Stack

- **Backend:** Django 5.2 + Django REST Framework (DRF)
- **Frontend:** React 18 + TypeScript + Vite + Tailwind CSS
- **Database:** PostgreSQL (with SQLite zero-config fallback for quick local testing)
- **Authentication:** JWT (SimpleJWT) + Email OTP verification + TOTP MFA + Google Sign-In (OAuth 2.0)
- **Document & Media Engine:** Pillow (PIL) + PyPDFium2
- **Email Service:** Centralized SMTP configuration with automated certificate delivery

---

## 🚀 Quick Start Guide

For full detailed setup instructions on another laptop, see the [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md).

### 1. Prerequisites
- **Python 3.10+** (Python 3.12 recommended)
- **Node.js 20 LTS** and **npm**
- **Git**
- **PostgreSQL** (or use `DB_ENGINE=sqlite` in `.env`)

---

### 2. Backend Setup

```bash
# Navigate to backend
cd backend

# Create & activate virtual environment (Windows PowerShell)
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create your own ignored local config (never copy another developer's .env)
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

# Run database migrations
python manage.py migrate

# Create initial admin superuser
python manage.py createsuperuser

# Start Django development server
python manage.py runserver 8005
```
- Backend API: `http://127.0.0.1:8005/api/`
- Django Admin: `http://127.0.0.1:8005/admin/`

---

### 3. Frontend Setup

In a new terminal window:

```bash
# Navigate to frontend
cd frontend

# Install exact dependencies from the committed lockfile
npm ci

# Create your own ignored local frontend config if needed
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

# Start React Vite development server
npm run dev
```
- Frontend Web App: `http://localhost:5173/`

---

## 💡 Key Features

- **Multi-Role Dashboards:**
  - **Admin Dashboard (`/admin`):** Issue certificates singly or from CSV, manage courses and templates, and review verification and audit records.
  - **Student / Recipient Dashboard (`/dashboard`):** View certificates associated with the account, claim eligible certificates after email verification, download available certificate files, and review verification history.
  - **Public Verification (`/verify`):** Check a certificate ID against the stored record and see its current status.
- **Dynamic Template Renderer:** Supports raster and PDF templates, saved text-layer positions and formatting, and certificate image/PDF output.
- **Account Security:** JWT sessions, email verification, TOTP MFA, password recovery, and audit records.

---

## 📚 Documentation
- [Comprehensive Multi-Laptop Setup Guide](docs/SETUP_GUIDE.md)
- [Database Schema](docs/DATABASE_SCHEMA.md)
- [API Contract](docs/API_CONTRACT.md)
