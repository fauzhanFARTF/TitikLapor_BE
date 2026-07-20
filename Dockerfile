FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_ENV=production \
    TZ=Asia/Jakarta \
    PORT=7860

# Dependensi GeoDjango (GDAL, GEOS, PROJ) — cukup paket runtime karena
# psycopg2-binary dan dependensi lain sudah tersedia dalam bentuk wheel.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gdal-bin \
        libgdal-dev \
        libgeos-dev \
        libproj-dev \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces menjalankan container sebagai UID 1000.
RUN useradd -m -u 1000 app
WORKDIR /home/app

# Requirements disalin lebih dulu agar layer pip ter-cache selama deps tetap.
COPY --chown=app:app requirements/ ./requirements/
RUN pip install --no-cache-dir -r requirements/production.txt

COPY --chown=app:app . .

RUN mkdir -p assets/static assets/media && chown -R app:app /home/app

USER app

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,os;urllib.request.urlopen(f\"http://127.0.0.1:{os.environ['PORT']}/api/v1/health/\")" || exit 1

# collectstatic dijalankan saat start karena variabel env baru tersedia di
# runtime (bukan saat build) pada sebagian besar platform PaaS.
CMD python manage.py migrate --noinput && \
    python manage.py collectstatic --noinput && \
    gunicorn config.wsgi:application \
        --bind 0.0.0.0:${PORT} \
        --workers 2 \
        --timeout 120 \
        --access-logfile - \
        --error-logfile -
