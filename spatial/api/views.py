"""Endpoint analisis spasial."""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

from core.exceptions import DomainError
from core.utils.responses import success
from spatial.api.serializers import (
    FasilitasGeoSerializer,
    RuteSerializer,
    WilayahGeoSerializer,
)
from spatial.models import Fasilitas, Wilayah
from spatial.services import spatial_service


def _ambil_koordinat(params) -> tuple[float, float]:
    try:
        return float(params["lat"]), float(params["lon"])
    except (KeyError, TypeError, ValueError) as exc:
        raise DomainError("Parameter lat & lon wajib berupa angka.") from exc


@api_view(["GET"])
@permission_classes([AllowAny])
def wilayah_geojson(request):
    """Batas wilayah administratif sebagai FeatureCollection."""

    tingkat = request.query_params.get("tingkat", Wilayah.Tingkat.KECAMATAN)
    qs = Wilayah.objects.filter(tingkat=tingkat)
    return success(WilayahGeoSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def agregasi_wilayah(request):
    """Jumlah & rasio penyelesaian laporan per wilayah (choropleth)."""

    tingkat = request.query_params.get("tingkat", Wilayah.Tingkat.KECAMATAN)
    return success(spatial_service.agregasi_per_wilayah(tingkat))


@api_view(["GET"])
@permission_classes([AllowAny])
def heatmap(request):
    status = request.query_params.getlist("status") or None
    return success(spatial_service.titik_heatmap(status))


@api_view(["GET"])
@permission_classes([AllowAny])
def reverse_wilayah(request):
    """Tentukan kelurahan/kecamatan dari satu koordinat."""

    lat, lon = _ambil_koordinat(request.query_params)
    return success(spatial_service.wilayah_dari_titik(lat, lon))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def laporan_sekitar(request):
    lat, lon = _ambil_koordinat(request.query_params)
    radius = float(request.query_params.get("radius", 1000))
    return success(spatial_service.laporan_sekitar(lat, lon, radius))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def fasilitas_terdekat(request):
    lat, lon = _ambil_koordinat(request.query_params)
    return success(
        spatial_service.fasilitas_terdekat(lat, lon, request.query_params.get("jenis"))
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def fasilitas_geojson(request):
    qs = Fasilitas.objects.select_related("instansi").all()
    if jenis := request.query_params.get("jenis"):
        qs = qs.filter(jenis=jenis)
    return success(FasilitasGeoSerializer(qs, many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def rute(request):
    """Rute menuju titik laporan untuk petugas lapangan."""

    serializer = RuteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    return success(
        spatial_service.hitung_rute(
            asal=(data["asal_lon"], data["asal_lat"]),
            tujuan=(data["tujuan_lon"], data["tujuan_lat"]),
            mesin=data.get("mesin"),
        )
    )
