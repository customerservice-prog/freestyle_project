from __future__ import annotations

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# -------------------------
# Core
# -------------------------

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-secret-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") in ("1", "true", "True", "yes", "YES")
ALLOWED_HOSTS = (
    os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if not DEBUG
    else ["*"]
)

# If you're behind a proxy (Render/Heroku/etc), you may need:
# SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# -------------------------
# Apps
# -------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # your app
    "freestyle",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",  # optional project-level templates folder
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# -------------------------
# Database
# -------------------------
# Local default: sqlite
# Prod: set DATABASE_URL (e.g. postgres://...)
#
# IMPORTANT: sqlite cannot accept sslmode/OPTIONS. We strip them if sqlite.
#
# If you want SSL for Postgres, set it only when engine is not sqlite.

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{(BASE_DIR / 'db.sqlite3')}",
        conn_max_age=int(os.environ.get("DB_CONN_MAX_AGE", "0")),
    )
}

# If we're using sqlite, remove OPTIONS entirely (fixes your 'sslmode' crash).
if DATABASES["default"]["ENGINE"].endswith("sqlite3"):
    DATABASES["default"].pop("OPTIONS", None)
else:
    # For Postgres-like engines, you can enforce sslmode if desired:
    if os.environ.get("DB_SSLMODE", "").strip():
        DATABASES["default"].setdefault("OPTIONS", {})
        DATABASES["default"]["OPTIONS"]["sslmode"] = os.environ["DB_SSLMODE"].strip()
    # Common default for hosted Postgres:
    # DATABASES["default"].setdefault("OPTIONS", {})
    # DATABASES["default"]["OPTIONS"].setdefault("sslmode", "require")

# -------------------------
# Password validation
# -------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -------------------------
# I18N / Time
# -------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

# -------------------------
# Static / Media
# -------------------------
# Your video files live under MEDIA_ROOT/media/...

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# -------------------------
# Misc
# -------------------------

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Helpful in dev if you're calling API endpoints from same origin
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

# Optional: quieter logging (adjust as needed)
LOG_LEVEL = os.environ.get("DJANGO_LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
}
