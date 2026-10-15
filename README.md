# OneSmarter CertiVerify

Smart, tamper-proof Certificate Issuance and Verification System built with Django REST Framework and React.js.

---

## 🌟 Technology Stack

- **Backend:** Django 5.2 + Django REST Framework (DRF)
- **Frontend:** React 18 + TypeScript + Vite + Tailwind CSS
- **Database:** PostgreSQL (with SQLite zero-config fallback for quick local testing)
- **Authentication:** JWT (SimpleJWT) + Email OTP verification + TOTP MFA + Google Sign-In (OAuth 2.0)
- **Document & Media Engine:** Pillow (PIL) + PyPDF + PyPDFium2 + QRCode generator
- **Email Service:** Centralized SMTP configuration with automated certificate delivery

---

## 🚀 Quick Start Guide

For full detailed setup instructions on another laptop, see the [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md).

### 1. Prerequisites
- **Python 3.10+ / 3.11+ / 3.12+**
- **Node.js 18+ / 20+** and **npm**
- **Git**
- **PostgreSQL** (or use `DB_ENGINE=sqlite` in `.env`)

---

### 2. Backend Setup

```bash
# Navigate to backend
cd backend

# Create & activate virtual environment
# Windows (PowerShell):
python -m venv .venv
.\.venv\Scripts\activate

# macOS / Linux:
# python3 -m venv .venv
# source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Configure environment variables
# Windows: copy .env.example .env
# macOS/Linux: cp .env.example .env

# Run database migrations
python manage.py migrate

# Create initial admin superuser
python manage.py createsuperuser

# Start Django development server
python manage.py runserver 8000
```
- Backend API: `http://127.0.0.1:8000/api/`
- Django Admin: `http://127.0.0.1:8000/admin/`

---

### 3. Frontend Setup

In a new terminal window:

```bash
# Navigate to frontend
cd frontend

# Install Node dependencies
npm install

# Configure environment variables
# Windows: copy .env.example .env
# macOS/Linux: cp .env.example .env

# Start React Vite development server
npm run dev
```
- Frontend Web App: `http://localhost:5173/`

---

## 💡 Key Features

- **Multi-Role Dashboards:**
  - **Admin Dashboard (`/admin`):** Issue single certificates, bulk CSV certificate issuance, manage courses, upload custom templates (Figma PNG/JPG), track verification logs, view audit trail.
  - **Student / Recipient Dashboard (`/dashboard`):** View issued certificates, automatic claiming of certificates issued prior to registration, download PDF/PNG certificates, view verification links.
  - **Public Verification (`/verify`):** Instant verification by Certificate ID, QR code scan, or document upload with cryptographic tamper checking.
- **Dynamic Template Renderer:** Supports custom high-resolution Figma PNGs, JPEG templates, custom coordinates, font scaling, and automated QR code embedding.
- **LinkedIn Credential Sharing:** Direct one-click share to LinkedIn Certifications profile.
- **Enterprise Security:** JWT tokens, email OTP verification, TOTP two-factor authentication, rate-limiting, and immutable audit logs.

---

## 📚 Documentation
- [Comprehensive Multi-Laptop Setup Guide](docs/SETUP_GUIDE.md)
- [Database Schema](docs/DATABASE_SCHEMA.md)
- [API Contract](docs/API_CONTRACT.md)
