from django.contrib.gis import admin

from reports.models import Dukungan, Kategori, Laporan, RiwayatStatus, Tanggapan


@admin.register(Kategori)
class KategoriAdmin(admin.ModelAdmin):
    list_display = ("nama", "slug", "instansi_default", "sla_hari", "is_active")
    prepopulated_fields = {"slug": ("nama",)}
    list_filter = ("is_active", "instansi_default")


class RiwayatInline(admin.TabularInline):
    model = RiwayatStatus
    extra = 0
    readonly_fields = (
        "status_lama",
        "status_baru",
        "catatan",
        "nama_oleh",
        "created_at",
    )
    can_delete = False


@admin.register(Laporan)
class LaporanAdmin(admin.GISModelAdmin):
    list_display = (
        "nomor_tiket",
        "judul",
        "kategori",
        "status",
        "instansi",
        "created_at",
    )
    list_filter = ("status", "prioritas", "kategori", "instansi")
    search_fields = ("nomor_tiket", "judul", "alamat")
    readonly_fields = ("nomor_tiket", "created_at", "updated_at")
    inlines = [RiwayatInline]
    date_hierarchy = "created_at"


admin.site.register([Dukungan, Tanggapan])

admin.site.site_header = "Titik Lapor — Administrasi"
admin.site.site_title = "Titik Lapor"
admin.site.index_title = "Panel Administrasi"
