
"""
Django settings for OneSmarter-CertiVerify.
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# --------------------------------------------------
# BASE DIRECTORY AND ENVIRONMENT
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

# --------------------------------------------------
# SECURITY SETTINGS
# --------------------------------------------------

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "dev-only-change-this-key-before-deployment"
)

DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "DJANGO_ALLOWED_HOSTS",
        "localhost,127.0.0.1,10.151.34.218"
    ).split(",")
    if host.strip()
]

# --------------------------------------------------
# APPLICATIONS
# --------------------------------------------------

INSTALLED_APPS = [
    # Django built-in apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party apps
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",

    # CertiVerify apps
    "apps.accounts.apps.AccountsConfig",
    "apps.certificates.apps.CertificatesConfig",
    "apps.verification.apps.VerificationConfig",
    "apps.dashboard.apps.DashboardConfig",
    "apps.audit.apps.AuditConfig",
    "apps.notifications.apps.NotificationsConfig",
]

# --------------------------------------------------
# MIDDLEWARE
# --------------------------------------------------

# CorsMiddleware MUST appear before any response-generating middleware
# (especially SessionMiddleware and CommonMiddleware) so it can attach
# CORS headers to ALL responses, including 4xx/5xx and preflight replies.

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# --------------------------------------------------
# URL CONFIGURATION
# --------------------------------------------------

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --------------------------------------------------
# POSTGRESQL DATABASE
# --------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "certiverify_db"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "8000"),
        "CONN_MAX_AGE": 60,
    }
}

# --------------------------------------------------
# PASSWORD VALIDATION
# --------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]

# --------------------------------------------------
# DJANGO REST FRAMEWORK
# --------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# --------------------------------------------------
# SIMPLE JWT
# --------------------------------------------------

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
    # SimpleJWT defaults to 'username' field. The frontend sends the user's
    # email address in the 'username' field during login, which works because
    # RegisterSerializer sets username = email at registration time.
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# --------------------------------------------------
# CACHE — used by MFA rate limiting and OTP replay protection
# --------------------------------------------------
# LocMemCache is per-process and restarts when the server restarts.
# In production, replace with a Redis backend:
#   pip install django-redis
#   CACHES = {"default": {"BACKEND": "django_redis.cache.RedisCache", "LOCATION": "redis://127.0.0.1:6379/1", ...}}
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "certiverify_cache",
    }
}

# --------------------------------------------------
# CORS – DEVELOPMENT ORIGIN ALLOWLIST
# --------------------------------------------------
# Use an explicit allowlist. Never set CORS_ALLOW_ALL_ORIGINS = True
# while the app uses any form of credentials (JWT, sessions, cookies).

_cors_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
_cors_list = [o.strip() for o in _cors_env.split(",") if o.strip()]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",

    "http://10.151.34.218:5173",
] + _cors_list

# Include PUBLIC_FRONTEND_URL in CORS if configured
if os.getenv("PUBLIC_FRONTEND_URL"):
    _pub_origin = os.getenv("PUBLIC_FRONTEND_URL").strip().rstrip("/")
    if _pub_origin and _pub_origin not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append(_pub_origin)

CSRF_TRUSTED_ORIGINS = [
    o for o in CORS_ALLOWED_ORIGINS if o.startswith("https://") or o.startswith("http://")
]

# The API authenticates via JWT Bearer tokens sent in the Authorization
# header, so CORS_ALLOW_CREDENTIALS is left at its default (False).
# No CSRF_TRUSTED_ORIGINS needed for pure JWT + JSON APIs.


# --------------------------------------------------
# INTERNATIONALIZATION
# --------------------------------------------------

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Kolkata"

USE_I18N = True

USE_TZ = True

# --------------------------------------------------
# STATIC AND MEDIA FILES
# --------------------------------------------------

STATIC_URL = "static/"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# --------------------------------------------------
# DEFAULT PRIMARY KEY
# --------------------------------------------------

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------
# EMAIL CONFIGURATION & RECOVERY
# --------------------------------------------------

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.ionos.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "akshay.kumar@onesmarter.com")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() == "true"
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "20"))
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    "OneSmarter Support <support@onesmarter.com>",
)
SERVER_EMAIL = os.getenv("SERVER_EMAIL", "support@onesmarter.com")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
# Public website URL used for LinkedIn Credential URLs and public verification
PUBLIC_FRONTEND_URL = os.getenv("PUBLIC_FRONTEND_URL", "").strip().rstrip("/")

# --------------------------------------------------
# GOOGLE OAUTH 2.0 / GOOGLE IDENTITY SERVICES
# --------------------------------------------------
GOOGLE_OAUTH_CLIENT_ID = os.getenv(
    "GOOGLE_CLIENT_ID",
    os.getenv("GOOGLE_OAUTH_CLIENT_ID", "668146604297-onesmarter-certiverify.apps.googleusercontent.com")
).strip()
