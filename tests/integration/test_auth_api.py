"""Pengujian integrasi autentikasi & otorisasi peran."""

import pytest
from rest_framework.test import APIClient

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_registrasi_selalu_menghasilkan_peran_warga():
    """Payload nakal yang menyisipkan role tidak boleh menaikkan hak akses."""

    response = APIClient().post(
        "/api/v1/auth/register/",
        {
            "email": "orang@contoh.id",
            "nama_lengkap": "Orang Baru",
            "password": "SandiSangatKuat123!",
            "password_konfirmasi": "SandiSangatKuat123!",
            "role": "ADMIN",
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.data["data"]["user"]["role"] == "WARGA"


def test_login_salah_tidak_membocorkan_email_terdaftar(warga):
    response = APIClient().post(
        "/api/v1/auth/login/",
        {"email": warga.email, "password": "sandi-salah"},
        format="json",
    )
    assert response.status_code == 400
    assert response.data["message"] == "Email atau kata sandi salah."


def test_login_berhasil_mengembalikan_pasangan_token(warga):
    response = APIClient().post(
        "/api/v1/auth/login/",
        {"email": warga.email, "password": "RahasiaKuat123!"},
        format="json",
    )
    assert response.status_code == 200
    assert {"access", "refresh"} <= set(response.data["data"]["tokens"])


def test_petugas_tidak_dapat_mengelola_pengguna(petugas):
    client = APIClient()
    client.force_authenticate(petugas)
    assert client.get("/api/v1/auth/pengguna/").status_code == 403


def test_health_check_terbuka():
    response = APIClient().get("/api/v1/health/")
    assert response.status_code == 200
    assert response.data["data"]["service"] == "titiklapor-api"
