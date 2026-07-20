"""Adapter fallback: jarak great-circle tanpa layanan eksternal.

Dipakai saat pengembangan lokal atau ketika OSRM tidak dapat dijangkau,
supaya fitur tetap memberi angka perkiraan alih-alih gagal total.
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from spatial.adapters.base import HasilRute, RoutingAdapter

RADIUS_BUMI_M = 6_371_000
# Faktor koreksi empiris jalan kota: jarak tempuh ±1,3x garis lurus.
FAKTOR_JALAN = 1.3
KECEPATAN_RATA_MPS = 8.3  # ~30 km/jam


def haversine(asal: tuple[float, float], tujuan: tuple[float, float]) -> float:
    lon1, lat1 = map(radians, asal)
    lon2, lat2 = map(radians, tujuan)
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * RADIUS_BUMI_M * asin(sqrt(a))


class NaiveAdapter(RoutingAdapter):
    nama = "naive"

    def rute(self, asal, tujuan) -> HasilRute:
        lurus = haversine(asal, tujuan)
        jarak = lurus * FAKTOR_JALAN
        return HasilRute(
            jarak_meter=round(jarak, 1),
            durasi_detik=round(jarak / KECEPATAN_RATA_MPS, 1),
            koordinat=[list(asal), list(tujuan)],
            penyedia=self.nama,
        )
