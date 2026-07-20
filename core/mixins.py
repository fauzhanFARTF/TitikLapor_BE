"""Mixin ViewSet bersama."""

from rest_framework.response import Response

from core.utils import responses


class EnvelopeResponseMixin:
    """Menyamakan bentuk response ViewSet dengan helper core.utils.responses.

    DRF generic view mengembalikan objek/list mentah; mixin ini membungkusnya
    agar frontend selalu membaca `response.data.data`.
    """

    def finalize_response(self, request, response, *args, **kwargs):
        if isinstance(response, Response) and response.status_code < 400:
            data = response.data
            already_wrapped = isinstance(data, dict) and "success" in data
            if not already_wrapped:
                response.data = {
                    "success": True,
                    "message": "Berhasil.",
                    "data": data,
                }
        return super().finalize_response(request, response, *args, **kwargs)


class SerializerActionMixin:
    """Memilih serializer berbeda per action lewat `serializer_action_classes`."""

    serializer_action_classes: dict = {}

    def get_serializer_class(self):
        return self.serializer_action_classes.get(
            self.action, super().get_serializer_class()
        )
