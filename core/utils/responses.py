"""Helper agar seluruh endpoint mengembalikan amplop response yang sama."""

from typing import Any

from rest_framework import status
from rest_framework.response import Response


def success(
    data: Any = None,
    message: str = "Berhasil.",
    http_status: int = status.HTTP_200_OK,
    meta: dict | None = None,
) -> Response:
    payload: dict[str, Any] = {"success": True, "message": message, "data": data}
    if meta is not None:
        payload["meta"] = meta
    return Response(payload, status=http_status)


def created(data: Any = None, message: str = "Data berhasil dibuat.") -> Response:
    return success(data, message, status.HTTP_201_CREATED)


def failure(
    message: str = "Permintaan gagal diproses.",
    errors: Any = None,
    http_status: int = status.HTTP_400_BAD_REQUEST,
    code: str = "error",
) -> Response:
    return Response(
        {"success": False, "message": message, "code": code, "errors": errors},
        status=http_status,
    )
