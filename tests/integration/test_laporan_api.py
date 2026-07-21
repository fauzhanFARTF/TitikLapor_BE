"""Pengujian integrasi endpoint laporan (butuh database PostGIS)."""

import pytest
from rest_framework.test import APIClient

from reports.models import Laporan

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture
def client_warga(warga) -> APIClient:
    client = APIClient()
    client.force_authenticate(warga)
    return client


@pytest.fixture
def client_petugas(petugas) -> APIClient:
    client = APIClient()
    client.force_authenticate(petugas)
    return client


def test_warga_dapat_membuat_laporan(client_warga, kategori):
    response = client_warga.post(
        "/api/v1/laporan/",
        {
            "judul": "Lampu jalan mati",
            "deskripsi": "Sudah tiga malam gelap total.",
            "kategori_id": str(kategori.id),
            "latitude": -6.1751,
            "longitude": 106.8272,
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.data["data"]["nomor_tiket"].startswith("TL-")
    # Instansi tujuan diturunkan otomatis dari kategori.
    assert response.data["data"]["instansi"] is not None


def test_warga_hanya_melihat_laporannya_sendiri(
    client_warga, laporan, kategori, admin_user
):
    Laporan.objects.create(
        nomor_tiket="TL-20260101-BBBB",
        judul="Laporan orang lain",
        deskripsi="Bukan milik warga uji.",
        kategori=kategori,
        lokasi=laporan.lokasi,
        pelapor=admin_user,
    )
    response = client_warga.get("/api/v1/laporan/")
    assert response.status_code == 200
    assert len(response.data["data"]) == 1


def test_warga_tidak_dapat_mengubah_status(client_warga, laporan):
    response = client_warga.post(
        f"/api/v1/laporan/{laporan.id}/status/",
        {"status": "DIVERIFIKASI"},
        format="json",
    )
    assert response.status_code == 403


def test_petugas_memverifikasi_lalu_memproses(client_petugas, laporan):
    r1 = client_petugas.post(
        f"/api/v1/laporan/{laporan.id}/status/",
        {"status": "DIVERIFIKASI", "catatan": "Lokasi sesuai."},
        format="json",
    )
    assert r1.status_code == 200

    r2 = client_petugas.post(
        f"/api/v1/laporan/{laporan.id}/status/",
        {"status": "DIPROSES"},
        format="json",
    )
    assert r2.status_code == 200
    laporan.refresh_from_db()
    assert laporan.diverifikasi_at is not None
    assert laporan.diproses_at is not None


def test_lompat_status_ditolak(client_petugas, laporan):
    response = client_petugas.post(
        f"/api/v1/laporan/{laporan.id}/status/",
        {"status": "SELESAI", "catatan_penyelesaian": "Sudah ditambal."},
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "invalid_state_transition"


def test_penolakan_wajib_beralasan(client_petugas, laporan):
    response = client_petugas.post(
        f"/api/v1/laporan/{laporan.id}/status/", {"status": "DITOLAK"}, format="json"
    )
    assert response.status_code == 400


def test_endpoint_lacak_tiket_terbuka_tanpa_login(laporan):
    response = APIClient().get(f"/api/v1/publik/lacak/{laporan.nomor_tiket}/")
    assert response.status_code == 200
    assert response.data["data"]["judul"] == laporan.judul


def test_daftar_laporan_menolak_permintaan_tanpa_token():
    assert APIClient().get("/api/v1/laporan/").status_code == 401
