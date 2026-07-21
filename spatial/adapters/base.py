"""Kontrak adapter mesin routing.

Aplikasi tidak boleh bergantung pada satu penyedia rute. Setiap penyedia
mengimplementasikan antarmuka ini, dan pilihan aktifnya ditentukan setting
`ROUTING_ENGINE` — sehingga pindah dari perhitungan naif ke OSRM (atau
Valhalla nanti) tidak menyentuh lapisan service.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class HasilRute:
    jarak_meter: float
    durasi_detik: float
    # Geometri rute sebagai daftar [lon, lat] — siap dipasang di Leaflet.
    koordinat: list[list[float]] = field(default_factory=list)
    penyedia: str = ""


class RoutingAdapter(ABC):
    nama: str = "base"

    @abstractmethod
    def rute(self, asal: tuple[float, float], tujuan: tuple[float, float]) -> HasilRute:
        """Hitung rute dari (lon, lat) asal ke (lon, lat) tujuan."""
        raise NotImplementedError
