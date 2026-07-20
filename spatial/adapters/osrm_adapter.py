"""Adapter OSRM (Open Source Routing Machine)."""

from __future__ import annotations

import logging

import requests
from django.conf import settings

from spatial.adapters.base import HasilRute, RoutingAdapter
from spatial.adapters.naive_adapter import NaiveAdapter

logger = logging.getLogger("spatial")

TIMEOUT_DETIK = 8


class OSRMAdapter(RoutingAdapter):
    nama = "osrm"

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.OSRM_BASE_URL).rstrip("/")

    def rute(self, asal, tujuan) -> HasilRute:
        url = (
            f"{self.base_url}/route/v1/driving/"
            f"{asal[0]},{asal[1]};{tujuan[0]},{tujuan[1]}"
        )
        try:
            response = requests.get(
                url,
                params={"overview": "full", "geometries": "geojson"},
                timeout=TIMEOUT_DETIK,
            )
            response.raise_for_status()
            payload = response.json()
            rute = payload["routes"][0]
        except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
            # Layanan rute pihak ketiga tidak boleh menjatuhkan request pengguna.
            logger.warning("OSRM gagal (%s), memakai perhitungan naif.", exc)
            return NaiveAdapter().rute(asal, tujuan)

        return HasilRute(
            jarak_meter=round(rute["distance"], 1),
            durasi_detik=round(rute["duration"], 1),
            koordinat=rute["geometry"]["coordinates"],
            penyedia=self.nama,
        )
