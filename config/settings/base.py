"""Setting dasar Titik Lapor — dipakai bersama oleh development & production."""

from datetime import timedelta
from pathlib import Path

import os

import environ

env = environ.Env()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env("SECRET_KEY", default="dev-only-insecure-key-ganti-di-produksi")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "django.contrib.postgres",
    # Third-party
    "rest_framework",
    "rest_framework_gis",
    "django_filters",
    "corsheaders",
    # Internal apps
    "core",
    "users",
    "reports",
    "spatial",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # Header keamanan tambahan (CSP, Permissions-Policy, COOP/CORP) yang tidak
    # dicakup SecurityMiddleware bawaan Django.
    "core.middleware.security_headers.SecurityHeadersMiddleware",
    # GZip memangkas payload GeoJSON yang besar (FeatureCollection laporan).
    "django.middleware.gzip.GZipMiddleware",
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
ASGI_APPLICATION = "config.asgi.application"

# ── Database (PostGIS) ────────────────────────────────────────────────────────

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": env("DB_NAME", default="titiklapor"),
        "USER": env("DB_USER", default="postgres"),
        "PASSWORD": env("DB_PASSWORD", default="postgres"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT", default="5432"),
        # Koneksi persisten — menghindari handshake Postgres baru tiap request.
        "CONN_MAX_AGE": env.int("DB_CONN_MAX_AGE", default=60),
        "CONN_HEALTH_CHECKS": True,
        # Supabase/Neon/RDS mewajibkan SSL → set DB_SSLMODE=require.
        "OPTIONS": {"sslmode": env("DB_SSLMODE", default="prefer")},
    },
}

# ── Auth ──────────────────────────────────────────────────────────────────────

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── DRF ───────────────────────────────────────────────────────────────────────

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_PAGINATION_CLASS": "core.utils.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "core.exception_handler.custom_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
}

# ── CORS ──────────────────────────────────────────────────────────────────────

CORS_ALLOWED_ORIGINS = env.list("CORS_ORIGINS", default=["http://localhost:5173"])
CORS_ALLOW_CREDENTIALS = True

# ── Static & Media ────────────────────────────────────────────────────────────

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "assets" / "static"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "assets" / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# ── Supabase Storage (media via S3-compatible API) ────────────────────────────
# Wajib di production bila filesystem host bersifat ephemeral (HF Spaces).

USE_SUPABASE_STORAGE = env.bool("USE_SUPABASE_STORAGE", default=False)

if USE_SUPABASE_STORAGE:
    INSTALLED_APPS = INSTALLED_APPS + ["storages"]

    _bucket = env("SUPABASE_STORAGE_BUCKET", default="titiklapor-media")
    _public_host = env("SUPABASE_S3_PUBLIC_HOST")

    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": _bucket,
            "endpoint_url": env("SUPABASE_S3_ENDPOINT"),
            "region_name": env("SUPABASE_S3_REGION", default="ap-southeast-1"),
            "access_key": env("SUPABASE_S3_ACCESS_KEY"),
            "secret_key": env("SUPABASE_S3_SECRET_KEY"),
            "custom_domain": f"{_public_host}/storage/v1/object/public/{_bucket}",
            "url_protocol": "https:",
            "default_acl": None,
            "querystring_auth": False,
            "file_overwrite": False,
            "addressing_style": "path",
        },
    }

# ── Lokalisasi ────────────────────────────────────────────────────────────────

LANGUAGE_CODE = "id-id"
TIME_ZONE = "Asia/Jakarta"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── GeoDjango ─────────────────────────────────────────────────────────────────
# Homebrew di macOS memasang GDAL/GEOS di path yang tidak terdeteksi otomatis.

_gdal_lib = env("GDAL_LIBRARY_PATH", default="")
if _gdal_lib:
    GDAL_LIBRARY_PATH = _gdal_lib

_geos_lib = env("GEOS_LIBRARY_PATH", default="")
if _geos_lib:
    GEOS_LIBRARY_PATH = _geos_lib

# SRID kerja aplikasi: WGS84 untuk penyimpanan, metrik untuk pengukuran.
SRID_WGS84 = 4326
SRID_METRIC = 3857

# ── Mesin routing eksternal (opsional) ───────────────────────────────────────

OSRM_BASE_URL = env("OSRM_BASE_URL", default="https://router.project-osrm.org")
ROUTING_ENGINE = env("ROUTING_ENGINE", default="naive")  # naive | osrm

# ── Header keamanan (dibaca SecurityHeadersMiddleware) ───────────────────────

SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Sumber tambahan yang boleh dimuat (mis. host media Supabase).
CSP_EXTRA_IMG_SRC = env.list("CSP_EXTRA_IMG_SRC", default=[])
CSP_EXTRA_CONNECT_SRC = env.list("CSP_EXTRA_CONNECT_SRC", default=[])
CSP_REPORT_ONLY = env.bool("CSP_REPORT_ONLY", default=False)

# ── Logging ───────────────────────────────────────────────────────────────────

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "core": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "users": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "reports": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "spatial": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
