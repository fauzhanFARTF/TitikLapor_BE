"""Analisis spasial: agregasi per wilayah, kepadatan, buffer & rute."""

from __future__ import annotations

import hashlib
import logging

from django.contrib.gis.db.models.functions import Centroid, Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.core.cache import cache
from django.db.models import Count, Q

from core.exceptions import DomainError
from reports.models import Laporan
from spatial.adapters import get_routing_adapter
from spatial.models import Fasilitas, Wilayah

logger = logging.getLogger("spatial")

CACHE_TTL_DETIK = 300


def _cache_key(prefix: str, *parts) -> str:
    sidik = hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:16]
    return f"spatial:{prefix}:{sidik}"


# ── Agregasi choropleth ──────────────────────────────────────────────────────


def agregasi_per_wilayah(tingkat: str = Wilayah.Tingkat.KECAMATAN) -> list[dict]:
    """Hitung jumlah laporan per wilayah lewat spatial join point-in-polygon.

    Hasilnya di-cache karena query ini menyentuh seluruh tabel laporan dan
    isinya hanya berubah saat ada laporan baru.
    """

    kunci = _cache_key("agregasi", tingkat)
    if (cached := cache.get(kunci)) is not None:
        return cached

    wilayah_qs = (
        Wilayah.objects.filter(tingkat=tingkat)
        .annotate(
            # `geom__contains` pada relasi terbalik = ST_Contains di PostGIS.
            total=Count("id", distinct=True, filter=Q(pk__isnull=False)),
        )
        .annotate(centroid=Centroid("geom"))
    )

    hasil = []
    for wilayah in wilayah_qs:
        laporan_qs = Laporan.objects.filter(lokasi__within=wilayah.geom)
        agg = laporan_qs.aggregate(
            total=Count("id"),
            selesai=Count("id", filter=Q(status=Laporan.Status.SELESAI)),
        )
        total = agg["total"] or 0
        hasil.append(
            {
                "id": str(wilayah.id),
                "kode": wilayah.kode,
                "nama": wilayah.nama,
                "tingkat": wilayah.tingkat,
                "total_laporan": total,
                "selesai": agg["selesai"],
                "persen_selesai": (
                    round(agg["selesai"] / total * 100, 1) if total else 0.0
                ),
                # Kepadatan per km² membuat wilayah besar & kecil sebanding.
                "kepadatan_per_km2": (
                    round(total / wilayah.luas_km2, 2) if wilayah.luas_km2 else None
                ),
                "centroid": [wilayah.centroid.x, wilayah.centroid.y],
            }
        )

    hasil.sort(key=lambda w: w["total_laporan"], reverse=True)
    cache.set(kunci, hasil, CACHE_TTL_DETIK)
    return hasil


def wilayah_dari_titik(latitude: float, longitude: float) -> dict | None:
    """Reverse-lookup wilayah administratif dari satu koordinat."""

    titik = Point(longitude, latitude, srid=4326)
    wilayah = (
        Wilayah.objects.filter(geom__contains=titik)
        .order_by("-tingkat")  # KELURAHAN lebih spesifik daripada KECAMATAN
        .first()
    )
    if wilayah is None:
        return None

    induk = wilayah.induk
    return {
        "id": str(wilayah.id),
        "nama": wilayah.nama,
        "kode": wilayah.kode,
        "tingkat": wilayah.tingkat,
        "induk": induk.nama if induk else None,
    }


# ── Kepadatan / heatmap ──────────────────────────────────────────────────────


def titik_heatmap(
    status: list[str] | None = None, batas: int = 5000
) -> list[list[float]]:
    """Daftar [lat, lon, bobot] untuk layer heatmap Leaflet.

    Bobot memakai jumlah dukungan supaya masalah yang dialami banyak warga
    tampak lebih pekat di peta.
    """

    qs = Laporan.objects.all()
    if status:
        qs = qs.filter(status__in=status)

    return [
        [lokasi.y, lokasi.x, min(1 + dukungan * 0.2, 5)]
        for lokasi, dukungan in qs.values_list("lokasi", "jumlah_dukungan")[:batas]
    ]


def laporan_sekitar(
    latitude: float, longitude: float, radius_meter: float = 1000, batas: int = 50
) -> list[dict]:
    """Laporan dalam radius tertentu, dari yang terdekat."""

    if radius_meter <= 0 or radius_meter > 50_000:
        raise DomainError("Radius harus di antara 1 dan 50.000 meter.")

    titik = Point(longitude, latitude, srid=4326)
    qs = (
        Laporan.objects.filter(lokasi__distance_lte=(titik, D(m=radius_meter)))
        .annotate(jarak=Distance("lokasi", titik))
        .select_related("kategori")
        .order_by("jarak")[:batas]
    )

    return [
        {
            "id": str(laporan.id),
            "nomor_tiket": laporan.nomor_tiket,
            "judul": laporan.judul,
            "kategori": laporan.kategori.nama,
            "status": laporan.status,
            "jarak_meter": round(laporan.jarak.m, 1),
            "latitude": laporan.lokasi.y,
            "longitude": laporan.lokasi.x,
        }
        for laporan in qs
    ]


# ── Fasilitas & rute ─────────────────────────────────────────────────────────


def fasilitas_terdekat(
    latitude: float, longitude: float, jenis: str | None = None, batas: int = 5
) -> list[dict]:
    titik = Point(longitude, latitude, srid=4326)
    qs = Fasilitas.objects.annotate(jarak=Distance("lokasi", titik)).order_by("jarak")
    if jenis:
        qs = qs.filter(jenis=jenis)

    return [
        {
            "id": str(f.id),
            "nama": f.nama,
            "jenis": f.jenis,
            "alamat": f.alamat,
            "jarak_meter": round(f.jarak.m, 1),
            "latitude": f.lokasi.y,
            "longitude": f.lokasi.x,
        }
        for f in qs[:batas]
    ]


def hitung_rute(
    asal: tuple[float, float], tujuan: tuple[float, float], mesin: str | None = None
) -> dict:
    """Rute dari petugas/fasilitas menuju titik laporan."""

    kunci = _cache_key("rute", asal, tujuan, mesin or "default")
    if (cached := cache.get(kunci)) is not None:
        return cached

    hasil = get_routing_adapter(mesin).rute(asal, tujuan)
    payload = {
        "jarak_meter": hasil.jarak_meter,
        "jarak_km": round(hasil.jarak_meter / 1000, 2),
        "durasi_detik": hasil.durasi_detik,
        "durasi_menit": round(hasil.durasi_detik / 60, 1),
        "koordinat": hasil.koordinat,
        "penyedia": hasil.penyedia,
    }
    cache.set(kunci, payload, CACHE_TTL_DETIK)
    return payload
