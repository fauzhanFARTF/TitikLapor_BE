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


class ResourceNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Data tidak ditemukan."
    default_code = "not_found"


class PermissionDeniedError(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Anda tidak berhak mengakses sumber daya ini."
    default_code = "permission_denied"
