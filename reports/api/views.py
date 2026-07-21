"""Endpoint laporan: CRUD, transisi status, peta, dan statistik."""

from django.contrib.gis.geos import Point
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

from core.exceptions import DomainError
from core.mixins import EnvelopeResponseMixin
from core.utils.responses import created, success
from reports.api.filters import LaporanFilter
from reports.api.serializers import (
    AlihkanInstansiSerializer,
    KategoriSerializer,
    LaporanCreateSerializer,
    LaporanDetailSerializer,
    LaporanGeoSerializer,
    LaporanListSerializer,
    TanggapanSerializer,
    UbahStatusSerializer,
)
from reports.models import Kategori, Laporan
from reports.repositories.laporan_repository import LaporanRepository
from reports.services import laporan_service
from users.permissions import IsAdmin, IsAdminOrPetugas


class KategoriViewSet(EnvelopeResponseMixin, viewsets.ModelViewSet):
    """Kategori laporan. Baca terbuka untuk publik, tulis khusus admin."""

    serializer_class = KategoriSerializer
    queryset = Kategori.objects.select_related("instansi_default").all()
    filterset_fields = ("is_active",)

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [IsAdmin()]


class LaporanViewSet(EnvelopeResponseMixin, viewsets.ModelViewSet):
    """Sumber daya utama. Baris yang terlihat dibatasi peran di service."""

    permission_classes = [IsAuthenticated]
    filterset_class = LaporanFilter
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = laporan_service.queryset_untuk(self.request.user)

        # Filter viewport peta: bbox=minLon,minLat,maxLon,maxLat
        bbox = self.request.query_params.get("bbox")
        if bbox:
            try:
                min_lon, min_lat, max_lon, max_lat = (float(v) for v in bbox.split(","))
            except ValueError as exc:
                raise DomainError(
                    "Parameter bbox harus berformat minLon,minLat,maxLon,maxLat."
                ) from exc
            qs = LaporanRepository.dalam_bbox(qs, min_lon, min_lat, max_lon, max_lat)

        # Filter radius: lat, lon, radius (meter)
        lat, lon = self.request.query_params.get("lat"), self.request.query_params.get(
            "lon"
        )
        if lat and lon:
            radius = float(self.request.query_params.get("radius", 1000))
            qs = LaporanRepository.dalam_radius(
                Point(float(lon), float(lat), srid=4326), radius, qs
            )
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return LaporanCreateSerializer
        if self.action in {"retrieve", "partial_update"}:
            return LaporanDetailSerializer
        return LaporanListSerializer

    def create(self, request, *args, **kwargs):
        serializer = LaporanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        laporan = laporan_service.buat_laporan(
            pelapor=request.user, **serializer.validated_data
        )
        return created(
            LaporanDetailSerializer(laporan, context={"request": request}).data,
            message=f"Laporan terkirim dengan nomor tiket {laporan.nomor_tiket}.",
        )

    def destroy(self, request, *args, **kwargs):
        laporan = self.get_object()
        # Pelapor boleh menarik laporannya sendiri selama belum diverifikasi.
        if request.user.is_warga:
            if laporan.pelapor_id != request.user.id:
                raise DomainError("Anda hanya dapat menarik laporan sendiri.")
            if laporan.status != Laporan.Status.BARU:
                raise DomainError("Laporan yang sudah diproses tidak dapat ditarik.")
        elif not request.user.is_admin:
            raise DomainError("Hanya administrator yang dapat menghapus laporan.")

        laporan.delete()  # soft delete — jejak audit tetap tersimpan
        return success(message="Laporan dihapus.")

    # ── Aksi ─────────────────────────────────────────────────────────────────

    @action(
        detail=True,
        methods=["post"],
        url_path="status",
        permission_classes=[IsAdminOrPetugas],
    )
    def ubah_status(self, request, pk=None):
        laporan = self.get_object()
        laporan_service.pastikan_boleh_ubah(laporan, request.user)

        serializer = UbahStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        laporan = laporan_service.ubah_status(
            laporan=laporan,
            status_baru=data["status"],
            oleh=request.user,
            catatan=data.get("catatan", ""),
            catatan_penyelesaian=data.get("catatan_penyelesaian", ""),
            foto_penyelesaian=data.get("foto_penyelesaian"),
        )
        return success(
            LaporanDetailSerializer(laporan, context={"request": request}).data,
            message="Status laporan diperbarui.",
        )

    @action(
        detail=True, methods=["post"], url_path="alihkan", permission_classes=[IsAdmin]
    )
    def alihkan(self, request, pk=None):
        serializer = AlihkanInstansiSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        laporan = laporan_service.alihkan_instansi(
            laporan=self.get_object(), oleh=request.user, **serializer.validated_data
        )
        return success(
            LaporanDetailSerializer(laporan, context={"request": request}).data,
            message="Laporan dialihkan ke instansi baru.",
        )

    @action(detail=True, methods=["post"], url_path="dukungan")
    def dukungan(self, request, pk=None):
        hasil = laporan_service.toggle_dukungan(
            laporan=self.get_object(), warga=request.user
        )
        return success(hasil, message="Dukungan diperbarui.")

    @action(detail=True, methods=["post"], url_path="tanggapan")
    def tanggapan(self, request, pk=None):
        serializer = TanggapanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tanggapan = laporan_service.tambah_tanggapan(
            laporan=self.get_object(),
            penulis=request.user,
            isi=serializer.validated_data["isi"],
            is_internal=request.data.get("is_internal") in (True, "true", "1"),
        )
        return created(
            TanggapanSerializer(tanggapan).data, message="Tanggapan terkirim."
        )

    @action(detail=False, methods=["get"], url_path="geojson")
    def geojson(self, request):
        """FeatureCollection untuk layer peta — tanpa paginasi."""

        qs = self.filter_queryset(self.get_queryset())[:2000]
        return success(LaporanGeoSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="statistik")
    def statistik(self, request):
        qs = self.filter_queryset(self.get_queryset())
        return success(
            {
                "ringkasan": LaporanRepository.statistik(qs),
                "per_kategori": LaporanRepository.per_kategori(qs),
                "tren_harian": LaporanRepository.tren_harian(qs),
            }
        )

    @action(detail=False, methods=["get"], url_path="cek-duplikat")
    def cek_duplikat(self, request):
        try:
            lat = float(request.query_params["lat"])
            lon = float(request.query_params["lon"])
            kategori_id = request.query_params["kategori_id"]
        except (KeyError, ValueError) as exc:
            raise DomainError(
                "Parameter lat, lon, dan kategori_id wajib diisi."
            ) from exc

        kandidat = laporan_service.cek_duplikat(lat, lon, kategori_id)
        return success(
            {
                "ada_duplikat": kandidat is not None,
                "laporan": (
                    LaporanListSerializer(kandidat, context={"request": request}).data
                    if kandidat
                    else None
                ),
            }
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def laporan_publik(request):
    """Peta publik: laporan sudah diverifikasi, tanpa perlu login."""

    qs = (
        LaporanRepository.base_queryset()
        .exclude(status__in=[Laporan.Status.BARU, Laporan.Status.DITOLAK])
        .order_by("-created_at")[:1000]
    )
    return success(LaporanGeoSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def lacak_tiket(request, nomor_tiket: str):
    """Pelacakan laporan lewat nomor tiket — tidak memerlukan akun."""

    laporan = LaporanRepository.get_by_tiket(nomor_tiket.upper())
    if laporan is None:
        raise DomainError("Nomor tiket tidak ditemukan.")

    return success(
        {
            "nomor_tiket": laporan.nomor_tiket,
            "judul": laporan.judul,
            "status": laporan.status,
            "status_label": laporan.get_status_display(),
            "kategori": laporan.kategori.nama,
            "instansi": laporan.instansi.nama if laporan.instansi else None,
            "created_at": laporan.created_at,
            "riwayat": [
                {
                    "status": r.status_baru,
                    "status_label": Laporan.Status(r.status_baru).label,
                    "catatan": r.catatan,
                    "waktu": r.created_at,
                }
                for r in laporan.riwayat.all()
            ],
        }
    )
