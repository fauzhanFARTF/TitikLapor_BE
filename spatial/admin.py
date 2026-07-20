from django.contrib.gis import admin

from spatial.models import Fasilitas, Wilayah


@admin.register(Wilayah)
class WilayahAdmin(admin.GISModelAdmin):
    list_display = ("nama", "kode", "tingkat", "induk", "jumlah_penduduk", "luas_km2")
    list_filter = ("tingkat",)
    search_fields = ("nama", "kode")


@admin.register(Fasilitas)
class FasilitasAdmin(admin.GISModelAdmin):
    list_display = ("nama", "jenis", "instansi", "alamat")
    list_filter = ("jenis", "instansi")
    search_fields = ("nama", "alamat")
