"""View utilitas lintas app."""

from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from core.utils.responses import success


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """Probe kesehatan untuk platform hosting & monitoring uptime."""

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_ok = True
    except Exception:  # noqa: BLE001 — health check tidak boleh melempar
        db_ok = False

    return success(
        {"service": "titiklapor-api", "version": "1.0.0", "database": db_ok},
        message="Layanan berjalan normal." if db_ok else "Database tidak terjangkau.",
    )
