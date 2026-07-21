"""Aturan bisnis laporan: penomoran tiket, transisi status, dan otorisasi data."""

from __future__ import annotations

import logging
import secrets
from datetime import date

from django.contrib.gis.geos import Point
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from core.exceptions import DomainError, InvalidStateTransition, PermissionDeniedError
from reports.models import Kategori, Laporan, Tanggapan
from reports.repositories.laporan_repository import LaporanRepository
from users.models import User

logger = logging.getLogger("reports")

# Transisi status yang sah. Kunci = status sekarang, nilai = tujuan yang boleh.
TRANSISI_SAH: dict[str, set[str]] = {
    Laporan.Status.BARU: {Laporan.Status.DIVERIFIKASI, Laporan.Status.DITOLAK},
    Laporan.Status.DIVERIFIKASI: {Laporan.Status.DIPROSES, Laporan.Status.DITOLAK},
    Laporan.Status.DIPROSES: {Laporan.Status.SELESAI, Laporan.Status.DITOLAK},
    Laporan.Status.SELESAI: set(),  # terminal
    Laporan.Status.DITOLAK: set(),  # terminal
}


def _generate_nomor_tiket() -> str:
    """Format TL-YYYYMMDD-XXXX; bagian acak mencegah tebak-tebakan nomor."""

    hari_ini = date.today().strftime("%Y%m%d")
    for _ in range(10):
        acak = secrets.token_hex(2).upper()
        nomor = f"TL-{hari_ini}-{acak}"
        if not Laporan.all_objects.filter(nomor_tiket=nomor).exists():
            return nomor
    raise DomainError("Gagal membuat nomor tiket unik. Coba lagi.")


# ── Pembuatan laporan ────────────────────────────────────────────────────────


@transaction.atomic
def buat_laporan(
    *,
    pelapor: User | None,
    judul: str,
    deskripsi: str,
    kategori_id,
    latitude: float,
    longitude: float,
    alamat: str = "",
    kelurahan: str = "",
    kecamatan: str = "",
    foto=None,
    is_anonim: bool = False,
) -> Laporan:
    kategori = Kategori.objects.filter(pk=kategori_id, is_active=True).first()
    if kategori is None:
        raise DomainError("Kategori tidak ditemukan atau sudah nonaktif.")

    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        raise DomainError("Koordinat lokasi tidak valid.")

    titik = Point(longitude, latitude, srid=4326)

    laporan = LaporanRepository.create(
        nomor_tiket=_generate_nomor_tiket(),
        judul=judul.strip(),
        deskripsi=deskripsi.strip(),
        kategori=kategori,
        # Instansi tujuan diturunkan dari kategori; admin bisa mengalihkan nanti.
        instansi=kategori.instansi_default,
        lokasi=titik,
        alamat=alamat.strip(),
        kelurahan=kelurahan.strip(),
        kecamatan=kecamatan.strip(),
        foto=foto,
        pelapor=pelapor,
        # Nama disalin agar riwayat tetap terbaca bila akun dihapus kelak.
        nama_pelapor="" if is_anonim else getattr(pelapor, "nama_lengkap", ""),
        is_anonim=is_anonim,
    )

    LaporanRepository.catat_riwayat(
        laporan, "", Laporan.Status.BARU, "Laporan dibuat.", pelapor
    )
    logger.info(
        "Laporan baru %s oleh %s", laporan.nomor_tiket, getattr(pelapor, "email", "-")
    )
    return laporan


def cek_duplikat(latitude: float, longitude: float, kategori_id) -> Laporan | None:
    """Peringatan dini duplikat: kategori sama, radius 50 m, 7 hari terakhir."""

    return LaporanRepository.duplikat_terdekat(
        Point(longitude, latitude, srid=4326), kategori_id
    )


# ── Transisi status ──────────────────────────────────────────────────────────


@transaction.atomic
def ubah_status(
    *, laporan: Laporan, status_baru: str, oleh: User, catatan: str = "", **extra
) -> Laporan:
    """Pindahkan laporan ke status berikutnya bila transisinya sah."""

    if status_baru not in Laporan.Status.values:
        raise DomainError("Status tujuan tidak dikenal.")

    status_lama = laporan.status
    if status_baru == status_lama:
        raise InvalidStateTransition("Laporan sudah berada pada status tersebut.")

    if status_baru not in TRANSISI_SAH[status_lama]:
        raise InvalidStateTransition(
            f"Tidak dapat mengubah status dari {laporan.get_status_display()} "
            f"ke {Laporan.Status(status_baru).label}."
        )

    if status_baru == Laporan.Status.DITOLAK and not catatan.strip():
        raise DomainError("Penolakan laporan wajib disertai alasan.")

    laporan.status = status_baru
    sekarang = timezone.now()
    kolom = ["status", "updated_at"]

    if status_baru == Laporan.Status.DIVERIFIKASI:
        laporan.diverifikasi_at = sekarang
        kolom.append("diverifikasi_at")
    elif status_baru == Laporan.Status.DIPROSES:
        laporan.diproses_at = sekarang
        laporan.petugas = oleh if oleh.is_petugas else laporan.petugas
        kolom += ["diproses_at", "petugas"]
    elif status_baru == Laporan.Status.SELESAI:
        if not extra.get("catatan_penyelesaian") and not catatan.strip():
            raise DomainError("Penyelesaian laporan wajib disertai catatan tindakan.")
        laporan.selesai_at = sekarang
        laporan.catatan_penyelesaian = extra.get("catatan_penyelesaian") or catatan
        kolom += ["selesai_at", "catatan_penyelesaian"]
        if extra.get("foto_penyelesaian"):
            laporan.foto_penyelesaian = extra["foto_penyelesaian"]
            kolom.append("foto_penyelesaian")

    laporan.save(update_fields=kolom)
    LaporanRepository.catat_riwayat(laporan, status_lama, status_baru, catatan, oleh)

    logger.info(
        "Laporan %s: %s → %s oleh %s",
        laporan.nomor_tiket,
        status_lama,
        status_baru,
        oleh.email,
    )
    return laporan


@transaction.atomic
def alihkan_instansi(
    *, laporan: Laporan, instansi_id, oleh: User, catatan: str = ""
) -> Laporan:
    """Disposisi laporan ke instansi lain (hak administrator)."""

    from users.models import Instansi

    instansi = Instansi.objects.filter(pk=instansi_id, is_active=True).first()
    if instansi is None:
        raise DomainError("Instansi tujuan tidak ditemukan atau nonaktif.")

    laporan.instansi = instansi
    laporan.petugas = None  # penugasan lama tidak lagi relevan
    laporan.save(update_fields=["instansi", "petugas", "updated_at"])

    LaporanRepository.catat_riwayat(
        laporan,
        laporan.status,
        laporan.status,
        catatan or f"Laporan dialihkan ke {instansi.nama}.",
        oleh,
    )
    return laporan


# ── Interaksi warga ──────────────────────────────────────────────────────────


@transaction.atomic
def toggle_dukungan(*, laporan: Laporan, warga: User) -> dict:
    """Tambah/batalkan dukungan warga; penghitung disimpan denormalisasi."""

    from reports.models import Dukungan

    # Dukungan dihapus permanen (bukan soft delete) supaya unique constraint
    # laporan+warga tidak menghalangi warga mendukung ulang di kemudian hari.
    dihapus, _ = Dukungan.all_objects.filter(laporan=laporan, warga=warga).hard_delete()
    if dihapus:
        didukung = False
    else:
        Dukungan.objects.create(laporan=laporan, warga=warga)
        didukung = True

    jumlah = Dukungan.objects.filter(laporan=laporan).count()
    laporan.jumlah_dukungan = jumlah
    laporan.save(update_fields=["jumlah_dukungan", "updated_at"])
    return {"didukung": didukung, "jumlah_dukungan": jumlah}


def tambah_tanggapan(
    *, laporan: Laporan, penulis: User, isi: str, is_internal: bool = False
) -> Tanggapan:
    if is_internal and penulis.is_warga:
        raise PermissionDeniedError("Warga tidak dapat menulis catatan internal.")

    return Tanggapan.objects.create(
        laporan=laporan,
        penulis=penulis,
        nama_penulis=penulis.nama_lengkap,
        peran_penulis=penulis.role,
        isi=isi.strip(),
        is_internal=is_internal,
    )


# ── Otorisasi tingkat data ───────────────────────────────────────────────────


def queryset_untuk(user: User) -> QuerySet[Laporan]:
    """Batasi baris yang boleh dilihat sesuai peran — bukan sekadar sembunyikan di UI."""

    qs = LaporanRepository.base_queryset()

    if user.is_admin:
        return qs
    if user.is_petugas:
        # Petugas hanya melihat laporan milik instansinya.
        return qs.filter(instansi_id=user.instansi_id)
    return qs.filter(pelapor_id=user.id)


def pastikan_boleh_ubah(laporan: Laporan, user: User) -> None:
    """Verifikasi & penanganan laporan hanya boleh oleh instansi terkait."""

    if user.is_admin:
        return
    if user.is_petugas and laporan.instansi_id == user.instansi_id:
        return
    raise PermissionDeniedError("Anda tidak berwenang mengubah laporan ini.")
