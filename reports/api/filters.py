"""Filter daftar laporan (django-filter)."""

import django_filters as filters

from reports.models import Laporan


class LaporanFilter(filters.FilterSet):
    status = filters.MultipleChoiceFilter(choices=Laporan.Status.choices)
    prioritas = filters.MultipleChoiceFilter(choices=Laporan.Prioritas.choices)
    kategori = filters.UUIDFilter(field_name="kategori_id")
    instansi = filters.UUIDFilter(field_name="instansi_id")
    kelurahan = filters.CharFilter(lookup_expr="iexact")
    kecamatan = filters.CharFilter(lookup_expr="iexact")
    dari = filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    sampai = filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    q = filters.CharFilter(method="filter_pencarian", label="Pencarian bebas")

    class Meta:
        model = Laporan
        fields = ("status", "prioritas", "kategori", "instansi")

    def filter_pencarian(self, queryset, name, value):
        from django.db.models import Q

        return queryset.filter(
            Q(judul__icontains=value)
            | Q(deskripsi__icontains=value)
            | Q(nomor_tiket__icontains=value)
            | Q(alamat__icontains=value)
        )
