"""Serializer data spasial."""

from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from spatial.models import Fasilitas, Wilayah


class WilayahGeoSerializer(GeoFeatureModelSerializer):
    """GeoJSON batas wilayah untuk layer choropleth."""

    class Meta:
        model = Wilayah
        geo_field = "geom"
        fields = ("id", "nama", "kode", "tingkat", "jumlah_penduduk", "luas_km2")


class FasilitasGeoSerializer(GeoFeatureModelSerializer):
    instansi_nama = serializers.CharField(
        source="instansi.nama", read_only=True, default=""
    )

    class Meta:
        model = Fasilitas
        geo_field = "lokasi"
        fields = ("id", "nama", "jenis", "alamat", "instansi_nama")


class RuteSerializer(serializers.Serializer):
    asal_lat = serializers.FloatField(min_value=-90, max_value=90)
    asal_lon = serializers.FloatField(min_value=-180, max_value=180)
    tujuan_lat = serializers.FloatField(min_value=-90, max_value=90)
    tujuan_lon = serializers.FloatField(min_value=-180, max_value=180)
    mesin = serializers.ChoiceField(choices=["naive", "osrm"], required=False)
