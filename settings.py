from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent

INSTALLED_APPS = [
    # ...
    "django.contrib.staticfiles",
    # ...
    "freestyle",
]

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]   # make sure BASE_DIR/static exists
STATIC_ROOT = BASE_DIR / "staticfiles"     # for collectstatic (production)

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
