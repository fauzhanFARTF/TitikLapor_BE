"""Serializer laporan — termasuk varian GeoJSON untuk peta."""

from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from reports.models import Dukungan, Kategori, Laporan, RiwayatStatus, Tanggapan


class KategoriSerializer(serializers.ModelSerializer):
    instansi_nama = serializers.CharField(
        source="instansi_default.nama", read_only=True, default=""
    )
    jumlah_laporan = serializers.IntegerField(read_only=True)

    class Meta:
        model = Kategori
        fields = (
            "id",
            "nama",
            "slug",
            "ikon",
            "warna",
            "instansi_default",
            "instansi_nama",
            "sla_hari",
            "is_active",
            "jumlah_laporan",
        )
        read_only_fields = ("id", "jumlah_laporan")


class RiwayatStatusSerializer(serializers.ModelSerializer):
    status_label = serializers.SerializerMethodField()

    class Meta:
        model = RiwayatStatus
        fields = (
            "id",
            "status_lama",
            "status_baru",
            "status_label",
            "catatan",
            "nama_oleh",
            "created_at",
        )

    def get_status_label(self, obj) -> str:
        return Laporan.Status(obj.status_baru).label


class TanggapanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tanggapan
        fields = (
            "id",
            "isi",
            "nama_penulis",
            "peran_penulis",
            "is_internal",
            "created_at",
        )
        read_only_fields = ("id", "nama_penulis", "peran_penulis", "created_at")


class LaporanListSerializer(serializers.ModelSerializer):
    """Payload ringan untuk daftar & kartu laporan."""

    kategori_nama = serializers.CharField(source="kategori.nama", read_only=True)
    kategori_warna = serializers.CharField(source="kategori.warna", read_only=True)
    kategori_ikon = serializers.CharField(source="kategori.ikon", read_only=True)
    instansi_nama = serializers.CharField(
        source="instansi.nama", read_only=True, default=""
    )
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    latitude = serializers.FloatField(read_only=True)
    longitude = serializers.FloatField(read_only=True)
    pelapor_nama = serializers.SerializerMethodField()

    class Meta:
        model = Laporan
        fields = (
            "id",
            "nomor_tiket",
            "judul",
            "kategori",
            "kategori_nama",
            "kategori_warna",
            "kategori_ikon",
            "instansi",
            "instansi_nama",
            "status",
            "status_label",
            "prioritas",
            "latitude",
            "longitude",
            "alamat",
            "kelurahan",
            "kecamatan",
            "foto",
            "pelapor_nama",
            "jumlah_dukungan",
            "created_at",
        )

    def get_pelapor_nama(self, obj) -> str:
        return "Anonim" if obj.is_anonim else (obj.nama_pelapor or "Warga")


class LaporanDetailSerializer(LaporanListSerializer):
    """Payload lengkap satu laporan, termasuk linimasa & tanggapan."""

    riwayat = RiwayatStatusSerializer(many=True, read_only=True)
    tanggapan = serializers.SerializerMethodField()
    petugas_nama = serializers.CharField(
        source="petugas.nama_lengkap", read_only=True, default=""
    )
    sudah_didukung = serializers.SerializerMethodField()

    class Meta(LaporanListSerializer.Meta):
        fields = LaporanListSerializer.Meta.fields + (
            "deskripsi",
            "petugas",
            "petugas_nama",
            "diverifikasi_at",
            "diproses_at",
            "selesai_at",
            "catatan_penyelesaian",
            "foto_penyelesaian",
            "riwayat",
            "tanggapan",
            "sudah_didukung",
            "updated_at",
        )

    def get_tanggapan(self, obj) -> list:
        user = self.context["request"].user
        qs = obj.tanggapan.all()
        # Catatan internal tidak boleh bocor ke warga/pelapor.
        if user.is_authenticated and user.is_warga:
            qs = qs.filter(is_internal=False)
        return TanggapanSerializer(qs, many=True).data

    def get_sudah_didukung(self, obj) -> bool:
        user = self.context["request"].user
        if not user.is_authenticated:
            return False
        return Dukungan.objects.filter(laporan=obj, warga=user).exists()


class LaporanCreateSerializer(serializers.Serializer):
    """Input pembuatan laporan; koordinat diterima sebagai lat/lon biasa."""

    judul = serializers.CharField(max_length=200)
    deskripsi = serializers.CharField()
    kategori_id = serializers.UUIDField()
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    alamat = serializers.CharField(max_length=255, required=False, allow_blank=True)
    kelurahan = serializers.CharField(max_length=100, required=False, allow_blank=True)
    kecamatan = serializers.CharField(max_length=100, required=False, allow_blank=True)
    foto = serializers.ImageField(required=False, allow_null=True)
    is_anonim = serializers.BooleanField(default=False)


class UbahStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Laporan.Status.choices)
    catatan = serializers.CharField(required=False, allow_blank=True, default="")
    catatan_penyelesaian = serializers.CharField(required=False, allow_blank=True)
    foto_penyelesaian = serializers.ImageField(required=False, allow_null=True)


class AlihkanInstansiSerializer(serializers.Serializer):
    instansi_id = serializers.UUIDField()
    catatan = serializers.CharField(required=False, allow_blank=True, default="")


class LaporanGeoSerializer(GeoFeatureModelSerializer):
    """Output GeoJSON FeatureCollection — dikonsumsi langsung oleh Leaflet."""

    kategori_nama = serializers.CharField(source="kategori.nama", read_only=True)
    kategori_warna = serializers.CharField(source="kategori.warna", read_only=True)
    kategori_ikon = serializers.CharField(source="kategori.ikon", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Laporan
        geo_field = "lokasi"
        fields = (
            "id",
            "nomor_tiket",
            "judul",
            "status",
            "status_label",
            "prioritas",
            "kategori_nama",
            "kategori_warna",
            "kategori_ikon",
            "alamat",
            "jumlah_dukungan",
            "created_at",
        )
