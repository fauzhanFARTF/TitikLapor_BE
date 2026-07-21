"""Routing app reports — dipasang di /api/v1/."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from reports.api.views import (
    KategoriViewSet,
    LaporanViewSet,
    lacak_tiket,
    laporan_publik,
)

router = DefaultRouter()
router.register("kategori", KategoriViewSet, basename="kategori")
router.register("laporan", LaporanViewSet, basename="laporan")

urlpatterns = [
    path("publik/laporan/", laporan_publik, name="laporan-publik"),
    path("publik/lacak/<str:nomor_tiket>/", lacak_tiket, name="lacak-tiket"),
    path("", include(router.urls)),
]
