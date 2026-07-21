"""Exception domain — dipetakan ke response HTTP oleh custom_exception_handler."""

from rest_framework import status
from rest_framework.exceptions import APIException


class DomainError(APIException):
    """Pelanggaran aturan bisnis (bukan kesalahan validasi field)."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Permintaan tidak dapat diproses."
    default_code = "domain_error"


class InvalidStateTransition(DomainError):
    default_detail = "Perubahan status laporan tidak diizinkan."
    default_code = "invalid_state_transition"


class TooManyRequests(APIException):
    """Batas laju terlampaui.

    django-ratelimit sendiri melempar `Ratelimited` yang berujung pada 403 —
    keliru secara semantik, karena masalahnya bukan izin melainkan frekuensi.
    View memakai `block=False` lalu melempar exception ini agar klien menerima
    429 beserta amplop error yang sama dengan endpoint lain.
    """

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Terlalu banyak percobaan. Coba lagi beberapa saat lagi."
    default_code = "too_many_requests"


class ResourceNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Data tidak ditemukan."
    default_code = "not_found"


class PermissionDeniedError(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Anda tidak berhak mengakses sumber daya ini."
    default_code = "permission_denied"
