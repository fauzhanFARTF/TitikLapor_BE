"""Pengujian pembatasan laju & pencabutan token.

Keduanya adalah pengaman yang hanya berguna kalau benar-benar menyala. Tanpa
pengujian, `django-ratelimit` yang terpasang tapi tidak pernah dipanggil akan
terlihat sama saja dengan yang bekerja.
"""

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def bersihkan_cache():
    """Penghitung rate limit tinggal di cache — sisa uji sebelumnya harus dibuang."""

    cache.clear()
    yield
    cache.clear()


# ── Pembatasan laju ─────────────────────────────────────────────────────────


def test_login_gagal_berulang_akhirnya_dibatasi(warga):
    """Batas per-email: 5 percobaan semenit, percobaan ke-6 ditolak 429."""

    client = APIClient()
    payload = {"email": warga.email, "password": "sandi-salah"}

    for ke in range(5):
        r = client.post("/api/v1/auth/login/", payload, format="json")
        assert r.status_code == 400, f"percobaan ke-{ke + 1} seharusnya masih dilayani"

    r = client.post("/api/v1/auth/login/", payload, format="json")
    assert r.status_code == 429
    assert r.data["code"] == "too_many_requests"


def test_pembatasan_login_terpisah_per_akun(warga, petugas):
    """Serangan pada satu akun tidak boleh mengunci akun lain dari IP sama."""

    client = APIClient()

    for _ in range(6):
        client.post(
            "/api/v1/auth/login/",
            {"email": warga.email, "password": "salah"},
            format="json",
        )

    # Akun berbeda, IP sama — masih di bawah batas per-IP (20/menit).
    r = client.post(
        "/api/v1/auth/login/",
        {"email": petugas.email, "password": "RahasiaKuat123!"},
        format="json",
    )
    assert r.status_code == 200


def test_registrasi_dibatasi_per_ip():
    """Batas 5 pendaftaran per jam menahan pembuatan akun massal."""

    client = APIClient()

    def daftar(n):
        return client.post(
            "/api/v1/auth/register/",
            {
                "email": f"orang{n}@contoh.id",
                "nama_lengkap": f"Orang {n}",
                "password": "SandiSangatKuat123!",
                "password_konfirmasi": "SandiSangatKuat123!",
            },
            format="json",
        )

    for n in range(5):
        assert daftar(n).status_code == 201

    assert daftar(99).status_code == 429


# ── Pencabutan token ────────────────────────────────────────────────────────


def _masuk(email: str) -> dict:
    r = APIClient().post(
        "/api/v1/auth/login/",
        {"email": email, "password": "RahasiaKuat123!"},
        format="json",
    )
    assert r.status_code == 200
    return r.data["data"]["tokens"]


def test_logout_mencabut_refresh_token(warga):
    """Inti perbaikan: setelah logout, refresh token tidak bisa dipakai lagi."""

    token = _masuk(warga.email)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token['access']}")
    assert (
        client.post(
            "/api/v1/auth/logout/", {"refresh": token["refresh"]}, format="json"
        ).status_code
        == 200
    )

    # Percobaan menukar token yang sudah dicabut harus gagal.
    r = APIClient().post(
        "/api/v1/auth/refresh/", {"refresh": token["refresh"]}, format="json"
    )
    assert r.status_code == 401


def test_refresh_token_lama_dicabut_setelah_rotasi(warga):
    """BLACKLIST_AFTER_ROTATION: token yang sudah ditukar tidak boleh dipakai ulang."""

    token = _masuk(warga.email)

    r1 = APIClient().post(
        "/api/v1/auth/refresh/", {"refresh": token["refresh"]}, format="json"
    )
    assert r1.status_code == 200

    # Token pertama sudah dirotasi — pemakaian ulang harus ditolak.
    r2 = APIClient().post(
        "/api/v1/auth/refresh/", {"refresh": token["refresh"]}, format="json"
    )
    assert r2.status_code == 401


def test_logout_menolak_permintaan_tanpa_autentikasi(warga):
    token = _masuk(warga.email)
    r = APIClient().post(
        "/api/v1/auth/logout/", {"refresh": token["refresh"]}, format="json"
    )
    assert r.status_code == 401


def test_logout_dengan_token_tak_berlaku_tetap_berhasil(warga):
    """Pengguna tidak perlu tahu tokennya sudah kedaluwarsa — hasilnya sama."""

    token = _masuk(warga.email)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token['access']}")

    r = client.post("/api/v1/auth/logout/", {"refresh": "token-ngawur"}, format="json")
    assert r.status_code == 200
