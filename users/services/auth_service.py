"""Logika bisnis autentikasi & registrasi.

View hanya mengurus HTTP; aturan domain (siapa boleh daftar sebagai apa,
peran mana yang wajib punya instansi) tinggal di lapisan ini supaya bisa
diuji tanpa request.
"""

from __future__ import annotations

import logging

from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from core.exceptions import DomainError
from users.models import Instansi, User

logger = logging.getLogger("users")


def issue_tokens(user: User) -> dict[str, str]:
    """Terbitkan pasangan token JWT beserta klaim peran."""

    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    refresh["nama_lengkap"] = user.nama_lengkap
    refresh["instansi_id"] = str(user.instansi_id) if user.instansi_id else None

    return {"refresh": str(refresh), "access": str(refresh.access_token)}


def login(email: str, password: str) -> tuple[User, dict[str, str]]:
    """Autentikasi kredensial email/password."""

    user = authenticate(username=email.lower().strip(), password=password)

    if user is None:
        # Pesan sengaja seragam agar tidak membocorkan email mana yang terdaftar.
        raise DomainError("Email atau kata sandi salah.")
    if not user.is_active:
        raise DomainError("Akun Anda dinonaktifkan. Hubungi administrator.")

    logger.info("Login berhasil: %s (%s)", user.email, user.role)
    return user, issue_tokens(user)


def logout(refresh_token: str) -> None:
    """Masukkan refresh token ke daftar cabut (blacklist).

    Setelah ini token tersebut tidak dapat lagi ditukar dengan access token
    baru, sehingga sesi benar-benar berakhir di sisi server — bukan sekadar
    dihapus dari penyimpanan browser.
    """

    try:
        RefreshToken(refresh_token).blacklist()
    except TokenError as exc:
        # Token kedaluwarsa atau sudah dicabut: hasil akhirnya sama saja bagi
        # pengguna, jadi jangan digagalkan — cukup dicatat.
        logger.info("Logout dengan token tidak berlaku: %s", exc)


@transaction.atomic
def register_warga(
    *, email: str, password: str, nama_lengkap: str, nomor_telepon: str = ""
) -> tuple[User, dict[str, str]]:
    """Registrasi mandiri hanya tersedia untuk peran WARGA.

    Akun PETUGAS & ADMIN dibuat administrator lewat endpoint terproteksi —
    pendaftaran publik tidak boleh bisa menaikkan peran sendiri.
    """

    email = email.lower().strip()

    if User.objects.filter(email=email).exists():
        raise DomainError("Email sudah terdaftar.")

    user = User.objects.create_user(
        email=email,
        password=password,
        nama_lengkap=nama_lengkap.strip(),
        nomor_telepon=nomor_telepon.strip(),
        role=User.Role.WARGA,
    )
    logger.info("Registrasi warga baru: %s", user.email)
    return user, issue_tokens(user)


@transaction.atomic
def create_internal_user(
    *,
    email: str,
    password: str,
    nama_lengkap: str,
    role: str,
    instansi_id: str | None = None,
    nomor_telepon: str = "",
) -> User:
    """Pembuatan akun internal (PETUGAS/ADMIN) oleh administrator."""

    if role not in {User.Role.PETUGAS, User.Role.ADMIN}:
        raise DomainError("Peran akun internal harus PETUGAS atau ADMIN.")

    if role == User.Role.PETUGAS and not instansi_id:
        raise DomainError("Akun petugas wajib ditautkan ke satu instansi.")

    if (
        instansi_id
        and not Instansi.objects.filter(pk=instansi_id, is_active=True).exists()
    ):
        raise DomainError("Instansi tidak ditemukan atau sudah nonaktif.")

    if User.objects.filter(email=email.lower().strip()).exists():
        raise DomainError("Email sudah terdaftar.")

    return User.objects.create_user(
        email=email,
        password=password,
        nama_lengkap=nama_lengkap.strip(),
        nomor_telepon=nomor_telepon.strip(),
        role=role,
        instansi_id=instansi_id,
        is_staff=role == User.Role.ADMIN,
    )
