"""Data referensi spasial: batas wilayah administratif & titik fasilitas."""

from django.contrib.gis.db import models as gis_models
from django.db import models

from core.models import BaseModel


class Wilayah(BaseModel):
    """Batas administratif (kecamatan/kelurahan) untuk agregasi choropleth."""

    class Tingkat(models.TextChoices):
        KOTA = "KOTA", "Kota/Kabupaten"
        KECAMATAN = "KECAMATAN", "Kecamatan"
        KELURAHAN = "KELURAHAN", "Kelurahan/Desa"

    nama = models.CharField(max_length=120, db_index=True)
    kode = models.CharField(max_length=20, unique=True, help_text="Kode wilayah BPS.")
    tingkat = models.CharField(max_length=12, choices=Tingkat.choices, db_index=True)
    induk = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="anak"
    )

    # MultiPolygon dipakai karena satu wilayah bisa terdiri dari beberapa
    # bagian terpisah (mis. kelurahan dengan enclave).
    geom = gis_models.MultiPolygonField(srid=4326, spatial_index=True)

    jumlah_penduduk = models.PositiveIntegerField(null=True, blank=True)
    luas_km2 = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "wilayah"
        verbose_name = "Wilayah"
        verbose_name_plural = "Wilayah"
        ordering = ["tingkat", "nama"]
        indexes = [models.Index(fields=["tingkat", "nama"])]

    def __str__(self) -> str:
        return f"{self.get_tingkat_display()} {self.nama}"


class Fasilitas(BaseModel):
    """Titik fasilitas publik (kantor dinas, posko) untuk analisis kedekatan."""

    class Jenis(models.TextChoices):
        KANTOR_DINAS = "KANTOR_DINAS", "Kantor Dinas"
        POSKO = "POSKO", "Posko Lapangan"
        PUSKESMAS = "PUSKESMAS", "Puskesmas"
        LAINNYA = "LAINNYA", "Lainnya"

    nama = models.CharField(max_length=150)
    jenis = models.CharField(max_length=15, choices=Jenis.choices, db_index=True)
    alamat = models.CharField(max_length=255, blank=True)
    lokasi = gis_models.PointField(srid=4326, geography=True, spatial_index=True)
    instansi = models.ForeignKey(
        "users.Instansi",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fasilitas",
    )

    class Meta:
        db_table = "fasilitas"
        verbose_name = "Fasilitas"
        verbose_name_plural = "Fasilitas"
        ordering = ["nama"]

    def __str__(self) -> str:
        return self.nama
