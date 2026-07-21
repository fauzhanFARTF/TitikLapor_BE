"""Routing app users — dipasang di /api/v1/auth/."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from users.api.views import (
    InstansiViewSet,
    UserViewSet,
    change_password_view,
    login_view,
    logout_view,
    profile_view,
    register_view,
)

router = DefaultRouter()
router.register("instansi", InstansiViewSet, basename="instansi")
router.register("pengguna", UserViewSet, basename="pengguna")

urlpatterns = [
    path("login/", login_view, name="auth-login"),
    path("logout/", logout_view, name="auth-logout"),
    path("register/", register_view, name="auth-register"),
    path("refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("profil/", profile_view, name="auth-profile"),
    path("ubah-sandi/", change_password_view, name="auth-change-password"),
    path("", include(router.urls)),
]
