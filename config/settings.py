from pathlib import Path
import os
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


# -------------------------
# Helpers
# -------------------------
def env(name: str, default: str | None = None) -> str | None:
    """
    Supports either NAME or DJANGO_NAME environment variables.
    Example: SECRET_KEY or DJANGO_SECRET_KEY
    """
    return os.environ.get(name) or os.environ.get(f"DJANGO_{name}") or default


def env_bool(name: str, default: str = "0") -> bool:
    val = (env(name, default) or "").strip().lower()
    return val in ("1", "true", "yes", "y", "on")


def split_csv(value: str) -> list[str]:
    cleaned = (value or "").replace(" ", "")
    return [x for x in cleaned.split(",") if x]


# -------------------------
# Core
# -------------------------
SECRET_KEY = env("SECRET_KEY", "dev-only-change-me")
DEBUG = env_bool("DEBUG", "1")

ALLOWED_HOSTS = split_csv(env("ALLOWED_HOSTS", "127.0.0.1,localhost"))

render_host = (env("RENDER_EXTERNAL_HOSTNAME") or "").strip()
if render_host and render_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_host)

# Allow Render internal hostnames / health checks
if ".onrender.com" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(".onrender.com")


# -------------------------
# Applications
# -------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "freestyle",

    # Only include this if you actually use tvapi right now.
    # If tvapi is removed from urls.py and not used, keep it commented.
    # "tvapi",
]


# -------------------------
# Middleware
# -------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # static on Render
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "config.urls"


# -------------------------
# Templates
# -------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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
# Default local fallback (SQLite)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Render Postgres (your shell shows DATABASE_URL exists)
database_url = env("DATABASE_URL")
if database_url:
    DATABASES["default"] = dj_database_url.parse(
        database_url,
        conn_max_age=600,
        ssl_require=True,
    )


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
# Internationalization
# -------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# -------------------------
# Static files
# -------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Django 5+ recommended storage setting
# In DEBUG, don't use Manifest (it can break if collectstatic not run)
if DEBUG:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }


# -------------------------
# Media uploads
# -------------------------
MEDIA_URL = "/media/"
# Local: BASE_DIR/media
# Render: set MEDIA_ROOT=/var/data/media (Disk mount)
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))


# -------------------------
# CSRF / Proxy SSL
# -------------------------
csrf_env = env("CSRF_TRUSTED_ORIGINS")
if csrf_env:
    CSRF_TRUSTED_ORIGINS = [x.strip() for x in csrf_env.split(",") if x.strip()]
else:
    CSRF_TRUSTED_ORIGINS = [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:8001",
        "http://localhost:8001",
    ]
    if render_host:
        CSRF_TRUSTED_ORIGINS.append(f"https://{render_host}")

# Render is behind a proxy (https outside, http inside)
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = False  # Render terminates SSL already


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
