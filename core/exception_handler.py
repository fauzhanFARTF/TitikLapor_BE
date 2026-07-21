"""Handler exception terpusat supaya seluruh error API berbentuk seragam."""

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("core")


def custom_exception_handler(exc, context):
    """Bungkus semua error menjadi {success, message, errors, code}."""

    if isinstance(exc, DjangoValidationError):
        return Response(
            {
                "success": False,
                "message": "Data yang dikirim tidak valid.",
                "code": "validation_error",
                "errors": (
                    exc.message_dict if hasattr(exc, "message_dict") else exc.messages
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    response = drf_exception_handler(exc, context)

    if response is None:
        # Error tak terduga: jangan bocorkan traceback ke klien.
        logger.exception("Unhandled exception pada %s", context.get("view"))
        return Response(
            {
                "success": False,
                "message": "Terjadi kesalahan internal pada server.",
                "code": "internal_error",
                "errors": None,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    detail = response.data
    code = getattr(exc, "default_code", "error")

    if isinstance(exc, Http404):
        message, errors = "Data tidak ditemukan.", None
        code = "not_found"
    elif isinstance(detail, dict) and set(detail.keys()) == {"detail"}:
        message, errors = str(detail["detail"]), None
    elif isinstance(detail, dict):
        message, errors = "Data yang dikirim tidak valid.", detail
        code = "validation_error"
    else:
        message, errors = "Permintaan gagal diproses.", detail

    response.data = {
        "success": False,
        "message": message,
        "code": code,
        "errors": errors,
    }
    return response
