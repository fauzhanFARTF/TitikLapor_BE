"""Setting production — HTTPS wajib, header keamanan penuh, static via WhiteNoise."""

import environ

from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE, STORAGES

env = environ.Env()

DEBUG = False

ALLOWED_HOSTS = env.list("HOSTS", default=[])

# ── HTTPS & HSTS ──────────────────────────────────────────────────────────────
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = 31536000 if SECURE_SSL_REDIRECT else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Di belakang reverse proxy (Nginx/HF Spaces) skema asli ada di header ini.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=SECURE_SSL_REDIRECT)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=SECURE_SSL_REDIRECT)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

CSP_REPORT_ONLY = env.bool("CSP_REPORT_ONLY", default=False)

# ── Static files (WhiteNoise) ────────────────────────────────────────────────
# Disisipkan tepat setelah SecurityMiddleware agar middleware baru di base.py
# tetap ikut terbawa tanpa menyalin ulang seluruh daftar.

MIDDLEWARE = list(MIDDLEWARE)
_security_idx = MIDDLEWARE.index("django.middleware.security.SecurityMiddleware")
MIDDLEWARE.insert(_security_idx + 1, "whitenoise.middleware.WhiteNoiseMiddleware")

STORAGES["staticfiles"][
    "BACKEND"
] = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ── Cache ─────────────────────────────────────────────────────────────────────

_redis_url = env("REDIS_URL", default="")
if _redis_url:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": _redis_url,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        }
    }
else:
    # PERINGATAN: LocMemCache bersifat per-proses. Pembatasan laju login
    # menyimpan penghitungnya di cache, sehingga dengan 2 worker gunicorn
    # batas efektifnya menjadi dua kali lipat dan penyerang cukup mencoba
    # berulang sampai mendarat di worker yang penghitungnya masih rendah.
    # Isi REDIS_URL bila layanan diekspos ke publik.
    CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    }
