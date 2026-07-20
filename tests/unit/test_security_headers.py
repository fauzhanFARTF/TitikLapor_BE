"""Pengujian header keamanan HTTP."""

import pytest
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from core.middleware.security_headers import SecurityHeadersMiddleware

pytestmark = pytest.mark.unit


def _respons(secure: bool = False):
    request = RequestFactory().get("/api/v1/health/", secure=secure)
    middleware = SecurityHeadersMiddleware(lambda r: HttpResponse("ok"))
    return middleware(request)


def test_header_wajib_selalu_terpasang():
    response = _respons()
    for header in (
        "Content-Security-Policy-Report-Only",  # development memakai report-only
        "Permissions-Policy",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
    ):
        assert header in response, f"{header} tidak terpasang"


def test_csp_tidak_mengizinkan_script_inline():
    csp = _respons()["Content-Security-Policy-Report-Only"]
    script_src = next(d for d in csp.split("; ") if d.startswith("script-src"))
    assert "'unsafe-inline'" not in script_src
    assert "'unsafe-eval'" not in script_src


def test_csp_melarang_penyematan_iframe():
    csp = _respons()["Content-Security-Policy-Report-Only"]
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp


def test_permissions_policy_mematikan_kamera_dan_mikrofon():
    policy = _respons()["Permissions-Policy"]
    assert "camera=()" in policy
    assert "microphone=()" in policy
    # Geolokasi tetap dibuka karena dipakai saat menandai lokasi laporan.
    assert "geolocation=(self)" in policy


@override_settings(
    SECURE_HSTS_SECONDS=31536000,
    SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
    SECURE_HSTS_PRELOAD=True,
)
def test_hsts_hanya_dikirim_pada_koneksi_https():
    assert "Strict-Transport-Security" not in _respons(secure=False)

    hsts = _respons(secure=True)["Strict-Transport-Security"]
    assert "max-age=31536000" in hsts
    assert "includeSubDomains" in hsts
    assert "preload" in hsts


@override_settings(CSP_REPORT_ONLY=False)
def test_mode_enforce_memakai_header_tanpa_report_only():
    request = RequestFactory().get("/")
    response = SecurityHeadersMiddleware(lambda r: HttpResponse())(request)
    assert "Content-Security-Policy" in response


def test_header_pembocor_stack_dihapus():
    request = RequestFactory().get("/")

    def view(_request):
        response = HttpResponse()
        response["Server"] = "gunicorn/23.0.0"
        return response

    assert "Server" not in SecurityHeadersMiddleware(view)(request)
