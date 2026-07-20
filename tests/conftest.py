"""Fixture bersama pengujian."""

import pytest
from django.contrib.gis.geos import Point

from reports.models import Kategori, Laporan
from users.models import Instansi, User


@pytest.fixture
def instansi(db) -> Instansi:
    return Instansi.objects.create(nama="Dinas PUPR", kode="DPUPR")


@pytest.fixture
def kategori(db, instansi) -> Kategori:
    return Kategori.objects.create(
        nama="Jalan Rusak", slug="jalan-rusak", instansi_default=instansi
    )


@pytest.fixture
def admin_user(db) -> User:
    return User.objects.create_user(
        email="admin@titiklapor.id",
        password="RahasiaKuat123!",
        nama_lengkap="Admin Uji",
        role=User.Role.ADMIN,
    )


@pytest.fixture
def petugas(db, instansi) -> User:
    return User.objects.create_user(
        email="petugas@titiklapor.id",
        password="RahasiaKuat123!",
        nama_lengkap="Petugas Uji",
        role=User.Role.PETUGAS,
        instansi=instansi,
    )


@pytest.fixture
def warga(db) -> User:
    return User.objects.create_user(
        email="warga@titiklapor.id",
        password="RahasiaKuat123!",
        nama_lengkap="Warga Uji",
        role=User.Role.WARGA,
    )


@pytest.fixture
def laporan(db, kategori, warga, instansi) -> Laporan:
    return Laporan.objects.create(
        nomor_tiket="TL-20260101-AAAA",
        judul="Lubang di Jalan Merdeka",
        deskripsi="Lubang cukup dalam, membahayakan pemotor.",
        kategori=kategori,
        instansi=instansi,
        lokasi=Point(106.8272, -6.1751, srid=4326),
        pelapor=warga,
        nama_pelapor=warga.nama_lengkap,
    )
