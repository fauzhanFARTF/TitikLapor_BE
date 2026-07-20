"""Akses data laporan.

Semua query kompleks (termasuk query spasial) dikumpulkan di sini supaya
service tidak bergantung pada detail ORM/PostGIS dan mudah di-mock saat uji.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from reports.models import Laporan, RiwayatStatus


class LaporanRepository:
    """Repository laporan — tanpa state, semua method boleh dipanggil statis."""

    @staticmethod
    def base_queryset() -> QuerySet[Laporan]:
        return Laporan.objects.select_related(
            "kategori", "instansi", "pelapor", "petugas"
        )

    @staticmethod
    def get_by_id(laporan_id) -> Laporan | None:
        return LaporanRepository.base_queryset().filter(pk=laporan_id).first()

    @staticmethod
    def get_by_tiket(nomor_tiket: str) -> Laporan | None:
        return (
            LaporanRepository.base_queryset().filter(nomor_tiket=nomor_tiket).first()
        )

    @staticmethod
    def create(**fields) -> Laporan:
        return Laporan.objects.create(**fields)

    # ── Query spasial ─────────────────────────────────────────────────────────

    @staticmethod
    def dalam_radius(
        titik: Point, radius_meter: float, qs: QuerySet[Laporan] | None = None
    ) -> QuerySet[Laporan]:
        """Laporan di dalam radius tertentu, diurutkan dari yang terdekat.

        Kolom `lokasi` bertipe geography sehingga jarak dihitung dalam meter
        di atas permukaan bumi — tidak perlu reproyeksi manual.
        """

        qs = qs if qs is not None else LaporanRepository.base_queryset()
        return (
            qs.filter(lokasi__distance_lte=(titik, D(m=radius_meter)))
            .annotate(jarak=Distance("lokasi", titik))
            .order_by("jarak")
        )

    @staticmethod
    def dalam_bbox(
        qs: QuerySet[Laporan], min_lon: float, min_lat: float, max_lon: float, max_lat: float
    ) -> QuerySet[Laporan]:
        """Filter berdasarkan viewport peta (bounding box)."""

        from django.contrib.gis.geos import Polygon

        bbox = Polygon.from_bbox((min_lon, min_lat, max_lon, max_lat))
        bbox.srid = 4326
        return qs.filter(lokasi__within=bbox)

    @staticmethod
    def duplikat_terdekat(
        titik: Point, kategori_id, radius_meter: float = 50, jendela_hari: int = 7
    ) -> Laporan | None:
        """Cari laporan sejenis di sekitar titik yang sama & masih baru.

        Dipakai service untuk memperingatkan warga sebelum membuat duplikat.
        """

        batas = timezone.now() - timedelta(days=jendela_hari)
        return (
            LaporanRepository.dalam_radius(titik, radius_meter)
            .filter(kategori_id=kategori_id, created_at__gte=batas)
            .exclude(status=Laporan.Status.DITOLAK)
            .first()
        )

    # ── Agregasi dashboard ────────────────────────────────────────────────────

    @staticmethod
    def statistik(qs: QuerySet[Laporan] | None = None) -> dict:
        qs = qs if qs is not None else Laporan.objects.all()
        agg = qs.aggregate(
            total=Count("id"),
            baru=Count("id", filter=Q(status=Laporan.Status.BARU)),
            diverifikasi=Count("id", filter=Q(status=Laporan.Status.DIVERIFIKASI)),
            diproses=Count("id", filter=Q(status=Laporan.Status.DIPROSES)),
            selesai=Count("id", filter=Q(status=Laporan.Status.SELESAI)),
            ditolak=Count("id", filter=Q(status=Laporan.Status.DITOLAK)),
        )
        total = agg["total"] or 0
        agg["persen_selesai"] = round(agg["selesai"] / total * 100, 1) if total else 0.0
        return agg

    @staticmethod
    def per_kategori(qs: QuerySet[Laporan] | None = None) -> list[dict]:
        qs = qs if qs is not None else Laporan.objects.all()
        return list(
            qs.values("kategori__nama", "kategori__warna")
            .annotate(jumlah=Count("id"))
            .order_by("-jumlah")
        )

    @staticmethod
    def tren_harian(qs: QuerySet[Laporan] | None = None, hari: int = 30) -> list[dict]:
        from django.db.models.functions import TruncDate

        qs = qs if qs is not None else Laporan.objects.all()
        sejak = timezone.now() - timedelta(days=hari)
        return list(
            qs.filter(created_at__gte=sejak)
            .annotate(tanggal=TruncDate("created_at"))
            .values("tanggal")
            .annotate(jumlah=Count("id"))
            .order_by("tanggal")
        )

    # ── Riwayat ───────────────────────────────────────────────────────────────

    @staticmethod
    def catat_riwayat(
        laporan: Laporan, status_lama: str, status_baru: str, catatan: str, oleh
    ) -> RiwayatStatus:
        return RiwayatStatus.objects.create(
            laporan=laporan,
            status_lama=status_lama,
            status_baru=status_baru,
            catatan=catatan,
            oleh=oleh,
            nama_oleh=getattr(oleh, "nama_lengkap", "") if oleh else "Sistem",
        )
