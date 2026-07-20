"""Setting development — DEBUG aktif, header keamanan dilonggarkan seperlunya."""

from .base import *  # noqa: F401,F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Tanpa TLS di lokal → redirect & cookie-secure dimatikan supaya login jalan.
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# CSP dijalankan report-only di lokal agar Vite HMR tidak terblokir.
CSP_REPORT_ONLY = True

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}
