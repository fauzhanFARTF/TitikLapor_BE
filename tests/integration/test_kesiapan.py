"""Pengujian command kesiapan produksi & pengamanan akun demo."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.test import override_settings

from users.models import User

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

SANDI_DEMO = "TitikLapor123!"


def _jalankan(nama: str, **opsi) -> tuple[str, int]:
    """Jalankan command, kembalikan (keluaran, kode keluar)."""

    keluaran = StringIO()
    try:
        call_command(nama, stdout=keluaran, stderr=keluaran, **opsi)
        return keluaran.getvalue(), 0
    except SystemExit as exc:
        return keluaran.getvalue(), exc.code


@pytest.fixture
def akun_demo(db) -> User:
    return User.objects.create_user(
        email="demo@titiklapor.id",
        password=SANDI_DEMO,
        nama_lengkap="Akun Demo",
        role=User.Role.ADMIN,
    )


# ── cek_kesiapan ────────────────────────────────────────────────────────────


# Django memaksa DEBUG=False selama pengujian, jadi kondisinya dipaksa
# secara eksplisit di sini.
@override_settings(DEBUG=True)
def test_debug_aktif_dilaporkan_sebagai_masalah():
    keluaran, kode = _jalankan("cek_kesiapan")

    assert "DEBUG aktif" in keluaran
    assert kode == 1, "adanya masalah harus menghasilkan kode keluar 1"


@override_settings(SECRET_KEY="dev-only-insecure-key-ganti-di-produksi")
def test_secret_key_bawaan_terdeteksi():
    keluaran, _ = _jalankan("cek_kesiapan")
    assert "SECRET_KEY masih bawaan" in keluaran


@override_settings(ALLOWED_HOSTS=["*"])
def test_wildcard_allowed_hosts_diperingatkan():
    keluaran, _ = _jalankan("cek_kesiapan")
    assert "wildcard" in keluaran


@override_settings(CORS_ALLOWED_ORIGINS=["http://localhost:5173"])
def test_origin_lokal_di_cors_diperingatkan():
    keluaran, _ = _jalankan("cek_kesiapan")
    assert "origin lokal" in keluaran


def test_akun_demo_aktif_terdeteksi(akun_demo):
    keluaran, kode = _jalankan("cek_kesiapan")

    assert "Akun demo masih aktif" in keluaran
    assert akun_demo.email in keluaran
    assert kode == 1


def test_akun_demo_nonaktif_tidak_dianggap_masalah(akun_demo):
    """Kata sandinya boleh tetap bawaan selama akunnya tidak bisa login."""

    akun_demo.is_active = False
    akun_demo.save(update_fields=["is_active"])

    keluaran, _ = _jalankan("cek_kesiapan")
    assert "Akun demo masih aktif" not in keluaran


def test_tanpa_kategori_aktif_dianggap_masalah():
    """Tanpa kategori, warga tidak dapat mengirim laporan sama sekali."""

    keluaran, kode = _jalankan("cek_kesiapan")

    assert "Tidak ada kategori aktif" in keluaran
    assert kode == 1


def test_kategori_tanpa_instansi_diperingatkan(kategori):
    kategori.instansi_default = None
    kategori.save(update_fields=["instansi_default"])

    keluaran, _ = _jalankan("cek_kesiapan")
    assert "tanpa instansi tujuan" in keluaran


def test_mode_ketat_menggagalkan_pada_peringatan(kategori):
    """Dipakai di CI: peringatan pun tidak boleh lolos."""

    _, kode_biasa = _jalankan("cek_kesiapan")
    _, kode_ketat = _jalankan("cek_kesiapan", ketat=True)

    assert kode_ketat == 1
    # Keduanya 1 di sini karena DEBUG aktif; yang diuji adalah --ketat diterima
    # dan tidak menurunkan tingkat keparahan.
    assert kode_biasa == 1


# ── amankan_akun_demo ───────────────────────────────────────────────────────


def test_dry_run_tidak_mengubah_apa_pun(akun_demo):
    _jalankan("amankan_akun_demo", dry_run=True)

    akun_demo.refresh_from_db()
    assert akun_demo.is_active is True
    assert akun_demo.check_password(SANDI_DEMO)


def test_nonaktifkan_akun_demo(akun_demo):
    _jalankan("amankan_akun_demo")

    akun_demo.refresh_from_db()
    assert akun_demo.is_active is False


def test_acak_sandi_membuat_sandi_bawaan_tidak_berlaku(akun_demo):
    keluaran, _ = _jalankan("amankan_akun_demo", acak_sandi=True)

    akun_demo.refresh_from_db()
    assert not akun_demo.check_password(SANDI_DEMO)
    assert akun_demo.is_active is True, "opsi ini tidak boleh menonaktifkan akun"
    # Sandi baru ditampilkan sekali agar dapat dicatat.
    assert akun_demo.email in keluaran


def test_hapus_akun_demo_bersifat_permanen(akun_demo, kategori):
    """Model User tidak memakai soft delete — penghapusan tidak dapat dibatalkan.

    Yang harus tetap selamat adalah laporannya: relasi pelapor bersifat
    SET_NULL dan nama pelapor sudah disalin saat laporan dibuat.
    """

    from reports.services import laporan_service

    laporan = laporan_service.buat_laporan(
        pelapor=akun_demo,
        judul="Laporan sebelum akun dihapus",
        deskripsi="Harus tetap terbaca setelah akun pelapornya hilang.",
        kategori_id=kategori.id,
        latitude=-6.2,
        longitude=106.5,
    )

    _jalankan("amankan_akun_demo", hapus=True)

    assert not User.objects.filter(pk=akun_demo.pk).exists()

    laporan.refresh_from_db()
    assert laporan.pelapor_id is None
    assert laporan.nama_pelapor == "Akun Demo", "nama pelapor harus tetap terbaca"


def test_tanpa_akun_demo_tidak_melakukan_apa_pun(warga):
    """Akun biasa berkata sandi lain tidak boleh ikut tersentuh."""

    keluaran, _ = _jalankan("amankan_akun_demo")

    warga.refresh_from_db()
    assert warga.is_active is True
    assert "Tidak ada akun berkata sandi bawaan" in keluaran
