"""Pemilih adapter routing berdasarkan setting ROUTING_ENGINE."""

from django.conf import settings

from spatial.adapters.base import HasilRute, RoutingAdapter
from spatial.adapters.naive_adapter import NaiveAdapter
from spatial.adapters.osrm_adapter import OSRMAdapter

ADAPTERS: dict[str, type[RoutingAdapter]] = {
    "naive": NaiveAdapter,
    "osrm": OSRMAdapter,
}


def get_routing_adapter(nama: str | None = None) -> RoutingAdapter:
    kunci = (nama or getattr(settings, "ROUTING_ENGINE", "naive")).lower()
    return ADAPTERS.get(kunci, NaiveAdapter)()


__all__ = ["HasilRute", "RoutingAdapter", "get_routing_adapter"]
