"""Header keamanan HTTP untuk respons API Titik Lapor.

`django.middleware.security.SecurityMiddleware` sudah menangani
Strict-Transport-Security, X-Content-Type-Options, dan Referrer-Policy lewat
setting bawaan. Yang belum dicakup Django adalah **Content-Security-Policy**
dan **Permissions-Policy** — dua header itu ditambahkan di sini, sekaligus
sebagai jaring pengaman kalau salah satu header bawaan hilang (mis. karena
respons dibuat oleh middleware lain yang menyela lebih awal).

Rangkuman header yang dijamin ada pada setiap respons:

| Header                    | Sumber                                   |
|---------------------------|------------------------------------------|
| Strict-Transport-Security | SecurityMiddleware (fallback di sini)    |
| Content-Security-Policy   | middleware ini                           |
| X-Frame-Options           | XFrameOptionsMiddleware (fallback di sini)|
| X-Content-Type-Options    | SecurityMiddleware (fallback di sini)    |
| Referrer-Policy           | SecurityMiddleware (fallback di sini)    |
| Permissions-Policy        | middleware ini                           |

Catatan CSP: API ini hanya menyajikan JSON plus halaman Django admin & DRF
browsable API. Keduanya butuh style inline, jadi `style-src` memuat
`'unsafe-inline'`; `script-src` sengaja TIDAK memuatnya.
"""

from __future__ import annotations

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

# Fitur browser yang dimatikan total — API tidak pernah membutuhkannya.
# Sintaks structured-header: `fitur=()` berarti tidak ada origin yang boleh.
PERMISSIONS_POLICY = ", ".join(
    (
        "accelerometer=()",
        "autoplay=()",
        "camera=()",
        "display-capture=()",
        "encrypted-media=()",
        "fullscreen=(self)",
        "geolocation=(self)",  # dipakai frontend untuk menandai lokasi laporan
        "gyroscope=()",
        "magnetometer=()",
        "microphone=()",
        "midi=()",
        "payment=()",
        "usb=()",
        "xr-spatial-tracking=()",
        "interest-cohort=()",  # opt-out FLoC
    )
)


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Menambahkan CSP & Permissions-Policy, plus fallback header bawaan."""

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self._csp_value = self._build_csp()
        self._csp_header = (
            "Content-Security-Policy-Report-Only"
            if getattr(settings, "CSP_REPORT_ONLY", False)
            else "Content-Security-Policy"
        )

    # ── Penyusunan CSP ────────────────────────────────────────────────────────

    @staticmethod
    def _build_csp() -> str:
        extra_img = getattr(settings, "CSP_EXTRA_IMG_SRC", []) or []
        extra_connect = getattr(settings, "CSP_EXTRA_CONNECT_SRC", []) or []

        directives: dict[str, list[str]] = {
            "default-src": ["'self'"],
            # Tanpa 'unsafe-inline'/'unsafe-eval' — admin & DRF tidak butuh.
            "script-src": ["'self'"],
            # Django admin & DRF browsable API memakai atribut style inline.
            "style-src": ["'self'", "'unsafe-inline'"],
            # data: untuk ikon inline, blob: untuk pratinjau unggahan foto.
            "img-src": ["'self'", "data:", "blob:", *extra_img],
            "font-src": ["'self'", "data:"],
            "connect-src": ["'self'", *extra_connect],
            "media-src": ["'self'", "blob:"],
            "object-src": ["'none'"],
            "base-uri": ["'self'"],
            "form-action": ["'self'"],
            "frame-ancestors": ["'none'"],
            "frame-src": ["'none'"],
            "worker-src": ["'self'", "blob:"],
            "manifest-src": ["'self'"],
        }

        parts = [f"{name} {' '.join(values)}" for name, values in directives.items()]

        # Paksa naikkan skema http:// pada sub-resource saat situs dilayani HTTPS.
        if getattr(settings, "SECURE_SSL_REDIRECT", False):
            parts.append("upgrade-insecure-requests")

        return "; ".join(parts)

    # ── Hook respons ──────────────────────────────────────────────────────────

    def process_response(self, request, response):
        # Content-Security-Policy — jangan timpa nilai yang diset view tertentu.
        response.setdefault(self._csp_header, self._csp_value)

        # Permissions-Policy — tidak ada padanan bawaannya di Django.
        response.setdefault("Permissions-Policy", PERMISSIONS_POLICY)

        # Isolasi lintas origin untuk halaman HTML (admin/browsable API).
        response.setdefault(
            "Cross-Origin-Opener-Policy",
            getattr(settings, "SECURE_CROSS_ORIGIN_OPENER_POLICY", "same-origin"),
        )
        # Resource API boleh diambil frontend beda origin → cross-origin.
        response.setdefault("Cross-Origin-Resource-Policy", "cross-origin")

        # ── Fallback untuk header yang biasanya diisi middleware bawaan ───────
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault(
            "X-Frame-Options", getattr(settings, "X_FRAME_OPTIONS", "DENY")
        )
        referrer_policy = getattr(settings, "SECURE_REFERRER_POLICY", None)
        if referrer_policy:
            response.setdefault("Referrer-Policy", referrer_policy)

        hsts_seconds = getattr(settings, "SECURE_HSTS_SECONDS", 0)
        if hsts_seconds and request.is_secure():
            value = f"max-age={hsts_seconds}"
            if getattr(settings, "SECURE_HSTS_INCLUDE_SUBDOMAINS", False):
                value += "; includeSubDomains"
            if getattr(settings, "SECURE_HSTS_PRELOAD", False):
                value += "; preload"
            response.setdefault("Strict-Transport-Security", value)

        # Header yang membocorkan detail stack — hapus bila ada.
        for leaky in ("Server", "X-Powered-By"):
            if leaky in response:
                del response[leaky]

        return response
