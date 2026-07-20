"""Adapter routing & fallback-nya."""

import pytest

from spatial.adapters import get_routing_adapter
from spatial.adapters.naive_adapter import NaiveAdapter, haversine

pytestmark = pytest.mark.unit

MONAS = (106.8272, -6.1754)
KOTA_TUA = (106.8133, -6.1352)


def test_haversine_mendekati_jarak_sebenarnya():
    """Monas → Kota Tua kurang lebih 4,6 km garis lurus."""

    jarak = haversine(MONAS, KOTA_TUA)
    assert 4_200 < jarak < 5_000


def test_jarak_titik_yang_sama_nol():
    assert haversine(MONAS, MONAS) == pytest.approx(0, abs=1e-6)


def test_adapter_naif_memberi_perkiraan_lebih_panjang_dari_garis_lurus():
    hasil = NaiveAdapter().rute(MONAS, KOTA_TUA)
    assert hasil.jarak_meter > haversine(MONAS, KOTA_TUA)
    assert hasil.durasi_detik > 0
    assert hasil.penyedia == "naive"


def test_nama_mesin_tak_dikenal_jatuh_ke_adapter_naif():
    assert isinstance(get_routing_adapter("mesin-yang-tidak-ada"), NaiveAdapter)
