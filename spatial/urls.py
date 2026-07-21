"""Routing app spatial — dipasang di /api/v1/spatial/."""

from django.urls import path

from spatial.api import views

urlpatterns = [
    path("wilayah/", views.wilayah_geojson, name="spatial-wilayah"),
    path("wilayah/agregasi/", views.agregasi_wilayah, name="spatial-agregasi"),
    path("wilayah/reverse/", views.reverse_wilayah, name="spatial-reverse"),
    path("heatmap/", views.heatmap, name="spatial-heatmap"),
    path("laporan-sekitar/", views.laporan_sekitar, name="spatial-laporan-sekitar"),
    path("fasilitas/", views.fasilitas_geojson, name="spatial-fasilitas"),
    path(
        "fasilitas/terdekat/", views.fasilitas_terdekat, name="spatial-fasilitas-dekat"
    ),
    path("rute/", views.rute, name="spatial-rute"),
]
