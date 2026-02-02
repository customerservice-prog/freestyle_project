# config/settings.py
from pathlib import Path
import os
import sys
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


# -------------------------
# Helpers
# -------------------------
def env(name: str, default=None):
    """Supports NAME or DJANGO_NAME."""
    return os.environ.get(name, os.environ.get(f"DJANGO_{name}", default))


def env_bool(name: str, default="0") -> bool:
    val = str(env(name, default)).strip().lower()
    return val in ("1", "true", "yes", "y", "on")


def split_csv(value) -> list[str]:
    cleaned = (value or "").replace(" ", "")
    return [x for x in cleaned.split(",") if x]


# -------------------------
# Core
# -------------------------
SECRET_KEY = env("SECRET_KEY", "dev-only-change-me")
DEBUG = env_bool("DEBUG", "0")

# Detect tests (so Client() host 'testserver' doesn't blow up)
RUNNING_TESTS = ("test" in sys.argv) or ("pytest" in sys.modules)

ALLOWED_HOSTS = split_csv(env("ALLOWED_HOSTS", "127.0.0.1,localhost"))

# Always allow testserver in DEBUG/tests (so your shell Client() works without SERVER_NAME)
if DEBUG or RUNNING_TESTS:
    if "testserver" not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append("testserver")

# Render hostname
render_host = (env("RENDER_EXTERNAL_HOSTNAME") or "").strip()
if render_host and render_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_host)

# allow onrender.com subdomains (healthchecks/internal)
if ".onrender.com" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(".onrender.com")

# Your real domain(s)
for host in ["bars24seven.com", "www.bars24seven.com"]:
    if host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)


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
]


# -------------------------
# Middleware
# -------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

database_url = env("DATABASE_URL")
if database_url:
    DATABASES["default"] = dj_database_url.parse(
        database_url,
        conn_max_age=600,
        ssl_require=False,
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
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}


# -------------------------
# Media (uploads)
# -------------------------
MEDIA_URL = env("MEDIA_URL", "/media/")
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))

# Only serve media from Django if explicitly enabled
# On Render with a persistent disk, you likely want SERVE_MEDIA=1
SERVE_MEDIA = env_bool("SERVE_MEDIA", "1" if DEBUG else "0")


# -------------------------
# CSRF / proxy
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
        "https://bars24seven.com",
        "https://www.bars24seven.com",
    ]
    if render_host:
        CSRF_TRUSTED_ORIGINS.append(f"https://{render_host}")

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = False  # Render terminates SSL

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# -------------------------
# Auth redirects
# -------------------------
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
