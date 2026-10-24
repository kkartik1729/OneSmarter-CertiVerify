"""
Django settings for OneSmarter-CertiVerify.
"""

import os
import sys
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured
from config.security import validate_django_secret_key

# --------------------------------------------------
# BASE DIRECTORY AND ENVIRONMENT
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

# --------------------------------------------------
# SECURITY SETTINGS
# --------------------------------------------------

try:
    SECRET_KEY = validate_django_secret_key(os.getenv("DJANGO_SECRET_KEY", ""))
except ValueError as exc:
    raise ImproperlyConfigured(
        str(exc)
    ) from exc

DJANGO_ENV = os.getenv("DJANGO_ENV", "production").strip().lower()
_debug_requested = os.getenv("DJANGO_DEBUG", "False").strip().lower() == "true"
if _debug_requested and DJANGO_ENV not in {"development", "local"}:
    raise ImproperlyConfigured(
        "DJANGO_DEBUG=True is allowed only when DJANGO_ENV is development or local."
    )
DEBUG = _debug_requested

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "DJANGO_ALLOWED_HOSTS",
        "localhost,127.0.0.1"
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
    "rest_framework_simplejwt.token_blacklist",
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
# DATABASE (PostgreSQL by default, SQLite supported via DB_ENGINE)
# --------------------------------------------------

_db_engine = os.getenv("DB_ENGINE", "django.db.backends.postgresql").strip().lower()

if _db_engine in ("sqlite", "sqlite3", "django.db.backends.sqlite3"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "certiverify_db"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
            # Fail promptly if PostgreSQL is unreachable. runserver checks
            # migration state before binding its HTTP port, so an unbounded
            # connection attempt otherwise looks like server startup is hung.
            "OPTIONS": {
                "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "5")),
            },
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
        "apps.accounts.authentication.SessionInvalidatingJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": (
        ["rest_framework.renderers.JSONRenderer"]
        if not DEBUG
        else [
            "rest_framework.renderers.JSONRenderer",
            "rest_framework.renderers.BrowsableAPIRenderer",
        ]
    ),
}

# --------------------------------------------------
# SIMPLE JWT
# --------------------------------------------------

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    # These defaults identify the user in JWT claims; login accepts a username
    # or complete email address in its `username` request field.
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
_USE_LOCAL_CACHE = DEBUG or "test" in sys.argv
CACHES = {
    "default": {
        "BACKEND": (
            "django.core.cache.backends.locmem.LocMemCache"
            if _USE_LOCAL_CACHE else "django.core.cache.backends.db.DatabaseCache"
        ),
        "LOCATION": "certiverify_cache",
    }
}

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "email_verification_ip": "10/hour",
    "password_reset_ip": "10/hour",
    "login_ip": "20/hour",
    "login_identity": "10/hour",
    "public_verification_ip": "60/minute",
}

# Production deployments terminate TLS at a trusted reverse proxy. Set
# SECURE_PROXY_SSL_HEADER only when that proxy strips client-supplied copies.
_proxy_header_name = os.getenv("DJANGO_SECURE_PROXY_HEADER", "").strip()
if _proxy_header_name:
    SECURE_PROXY_SSL_HEADER = (_proxy_header_name, "https")
TRUSTED_PROXY_IPS = tuple(
    value.strip()
    for value in os.getenv("DJANGO_TRUSTED_PROXY_IPS", "").split(",")
    if value.strip()
)
SECURE_SSL_REDIRECT = os.getenv(
    "DJANGO_SECURE_SSL_REDIRECT", "false" if DEBUG else "true"
).strip().lower() == "true"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", "31536000" if not DEBUG else "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG and os.getenv(
    "DJANGO_HSTS_INCLUDE_SUBDOMAINS", "true"
).strip().lower() == "true"
SECURE_HSTS_PRELOAD = not DEBUG and os.getenv(
    "DJANGO_HSTS_PRELOAD", "false"
).strip().lower() == "true"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

# Use Django's structured logging pipeline; emails and tokens must never be
# included in messages passed to these loggers.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
    },
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": os.getenv("DJANGO_LOG_LEVEL", "INFO")},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

# --------------------------------------------------
# CORS – DEVELOPMENT ORIGIN ALLOWLIST
# --------------------------------------------------
# Use an explicit allowlist. Never set CORS_ALLOW_ALL_ORIGINS = True
# while the app uses any form of credentials (JWT, sessions, cookies).

_cors_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
_cors_list = [o.strip() for o in _cors_env.split(",") if o.strip()]
_local_frontend_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
]

CORS_ALLOWED_ORIGINS = (_local_frontend_origins if DEBUG else []) + _cors_list

# Include the normalized public frontend URL in CORS if configured.
PUBLIC_FRONTEND_URL = os.getenv("PUBLIC_FRONTEND_URL", "").strip().rstrip("/")
if PUBLIC_FRONTEND_URL:
    _pub_origin = PUBLIC_FRONTEND_URL
    if _pub_origin and _pub_origin not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append(_pub_origin)

_csrf_env = os.getenv("CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_env.split(",") if o.strip()]
if DEBUG:
    CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(CSRF_TRUSTED_ORIGINS + _local_frontend_origins))

# The API authenticates via JWT Bearer tokens sent in the Authorization
# header, so CORS_ALLOW_CREDENTIALS is left at its default (False).
# No CSRF_TRUSTED_ORIGINS needed for pure JWT + JSON APIs.


# --------------------------------------------------
# INTERNATIONALIZATION
# --------------------------------------------------

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

# --------------------------------------------------
# STATIC AND MEDIA FILES
# --------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

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
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() == "true"
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "20"))
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    "OneSmarter Support <support@onesmarter.com>",
)
SERVER_EMAIL = os.getenv("SERVER_EMAIL", "support@onesmarter.com")
EMAIL_REPLY_TO = os.getenv("EMAIL_REPLY_TO", "help@onesmarter.com").strip()
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
# Public website URL used in certificate emails and CORS configuration

# --------------------------------------------------
# GOOGLE OAUTH 2.0 / GOOGLE IDENTITY SERVICES
# --------------------------------------------------
GOOGLE_OAUTH_CLIENT_ID = os.getenv(
    "GOOGLE_CLIENT_ID",
    os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
).strip()
