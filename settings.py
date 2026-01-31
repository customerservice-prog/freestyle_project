from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent


# -------------------------
# Environment helpers
# -------------------------
def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)

def env_bool(key: str, default: str = "0") -> bool:
    return env(key, default).strip().lower() in ("1", "true", "yes", "on")

def env_list(key: str, default: str = "") -> list[str]:
    """
    Accepts:
      "a.com,b.com,.onrender.com"
      "a.com, b.com, .onrender.com"
    Strips spaces and ignores blanks.
    """
    raw = env(key, default)
    return [h.strip() for h in raw.split(",") if h.strip()]


# -------------------------
# Core security / deploy
# -------------------------
DEBUG = env_bool("DEBUG", "0")

SECRET_KEY = env("SECRET_KEY", "dev-only-change-me")

ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost,.onrender.com"
)

# If you're using Django >= 4 and POSTing / logging into admin on HTTPS domains:
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")


# -------------------------
# Apps
# -------------------------
INSTALLED_APPS = [
    # ...
    "django.contrib.staticfiles",
    # ...
    "freestyle",
]


# -------------------------
# Static files (CSS/JS/images you ship)
# -------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# GOTCHA #1:
# STATICFILES_DIRS should be ONLY for local dev (extra directories to search),
# and should NOT be used the same way in production deployments.
# Also: never point STATICFILES_DIRS at STATIC_ROOT.
if DEBUG:
    STATICFILES_DIRS = [BASE_DIR / "static"]
else:
    STATICFILES_DIRS = []


# -------------------------
# Media files (user uploads / your mp4 library)
# -------------------------
MEDIA_URL = "/media/"

# GOTCHA #2:
# On Render, the filesystem is ephemeral unless you use a disk.
# If you mounted a disk at /var/data, store media there.
# (Your Render screenshot shows a disk mount path like /var/data.)
MEDIA_ROOT = Path(env("MEDIA_ROOT", "/var/data/media")) if not DEBUG else (BASE_DIR / "media")
