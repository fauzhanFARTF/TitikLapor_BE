"""Aturan transisi status laporan — inti dari alur kerja aplikasi."""

import pytest

from reports.models import Laporan
from reports.services.laporan_service import TRANSISI_SAH

pytestmark = pytest.mark.unit


def test_setiap_status_terdaftar_di_tabel_transisi():
    assert set(TRANSISI_SAH) == set(Laporan.Status.values)


def test_status_selesai_dan_ditolak_bersifat_terminal():
    assert TRANSISI_SAH[Laporan.Status.SELESAI] == set()
    assert TRANSISI_SAH[Laporan.Status.DITOLAK] == set()


def test_laporan_baru_tidak_bisa_langsung_selesai():
    """Melompati verifikasi & proses akan menghilangkan jejak audit."""

    assert Laporan.Status.SELESAI not in TRANSISI_SAH[Laporan.Status.BARU]


def test_penolakan_dapat_dilakukan_dari_setiap_status_aktif():
    aktif = [Laporan.Status.BARU, Laporan.Status.DIVERIFIKASI, Laporan.Status.DIPROSES]
    assert all(Laporan.Status.DITOLAK in TRANSISI_SAH[s] for s in aktif)


def test_alur_utama_dapat_ditempuh_berurutan():
    urutan = [
        Laporan.Status.BARU,
        Laporan.Status.DIVERIFIKASI,
        Laporan.Status.DIPROSES,
        Laporan.Status.SELESAI,
    ]
    for sekarang, berikutnya in zip(urutan, urutan[1:]):
        assert berikutnya in TRANSISI_SAH[sekarang]
