"""Endpoint autentikasi, profil, manajemen pengguna & instansi."""

from django.db.models import Count
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenRefreshView  # noqa: F401 (re-export)

from core.exceptions import DomainError
from core.mixins import EnvelopeResponseMixin
from core.utils.responses import created, success
from users.api.serializers import (
    ChangePasswordSerializer,
    CreateInternalUserSerializer,
    InstansiSerializer,
    LoginSerializer,
    RegisterWargaSerializer,
    UpdateProfileSerializer,
    UserSerializer,
)
from users.models import Instansi, User
from users.permissions import IsAdmin
from users.services import auth_service


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    """Login untuk semua peran (warga, petugas, admin)."""

    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user, tokens = auth_service.login(
        serializer.validated_data["email"], serializer.validated_data["password"]
    )
    return success(
        {"user": UserSerializer(user).data, "tokens": tokens},
        message="Login berhasil.",
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request):
    """Registrasi mandiri — peran selalu dipaksa WARGA di service."""

    serializer = RegisterWargaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    user, tokens = auth_service.register_warga(
        email=data["email"],
        password=data["password"],
        nama_lengkap=data["nama_lengkap"],
        nomor_telepon=data.get("nomor_telepon", ""),
    )
    return created(
        {"user": UserSerializer(user).data, "tokens": tokens},
        message="Pendaftaran berhasil.",
    )


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def profile_view(request):
    """Baca / perbarui profil pengguna yang sedang login."""

    if request.method == "GET":
        return success(UserSerializer(request.user).data)

    serializer = UpdateProfileSerializer(request.user, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return success(UserSerializer(request.user).data, message="Profil diperbarui.")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    serializer = ChangePasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = request.user
    if not user.check_password(serializer.validated_data["password_lama"]):
        raise DomainError("Kata sandi lama tidak sesuai.")

    user.set_password(serializer.validated_data["password_baru"])
    user.save(update_fields=["password", "updated_at"])
    return success(message="Kata sandi berhasil diubah.")


class InstansiViewSet(EnvelopeResponseMixin, viewsets.ModelViewSet):
    """CRUD instansi. Baca terbuka untuk pengguna login, tulis khusus admin."""

    serializer_class = InstansiSerializer
    queryset = Instansi.objects.annotate(jumlah_petugas=Count("petugas"))
    filterset_fields = ("is_active",)

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [IsAuthenticated()]
        return [IsAdmin()]


class UserViewSet(EnvelopeResponseMixin, viewsets.ReadOnlyModelViewSet):
    """Daftar pengguna untuk administrator, plus aksi pembuatan akun internal."""

    serializer_class = UserSerializer
    permission_classes = [IsAdmin]
    queryset = User.objects.select_related("instansi").all()
    filterset_fields = ("role", "instansi", "is_active")

    @action(detail=False, methods=["post"], url_path="internal")
    def create_internal(self, request):
        serializer = CreateInternalUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = auth_service.create_internal_user(
            email=data["email"],
            password=data["password"],
            nama_lengkap=data["nama_lengkap"],
            role=data["role"],
            instansi_id=data.get("instansi_id"),
            nomor_telepon=data.get("nomor_telepon", ""),
        )
        return created(UserSerializer(user).data, message="Akun internal dibuat.")

    @action(detail=True, methods=["post"], url_path="nonaktifkan")
    def deactivate(self, request, pk=None):
        user = self.get_object()
        if user.pk == request.user.pk:
            raise DomainError("Anda tidak dapat menonaktifkan akun sendiri.")
        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])
        return success(UserSerializer(user).data, message="Akun dinonaktifkan.")

    @action(detail=True, methods=["post"], url_path="aktifkan")
    def activate(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=["is_active", "updated_at"])
        return success(UserSerializer(user).data, message="Akun diaktifkan.")
