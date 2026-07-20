"""Permission class berbasis peran."""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdmin(BasePermission):
    message = "Hanya administrator yang boleh mengakses sumber daya ini."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)


class IsPetugas(BasePermission):
    message = "Hanya petugas instansi yang boleh mengakses sumber daya ini."

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user and request.user.is_authenticated and request.user.is_petugas
        )


class IsWarga(BasePermission):
    message = "Hanya akun warga yang boleh mengakses sumber daya ini."

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user and request.user.is_authenticated and request.user.is_warga
        )


class IsAdminOrPetugas(BasePermission):
    message = "Butuh akun petugas atau administrator."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and (user.is_admin or user.is_petugas))


class IsOwnerOrStaffReadOnly(BasePermission):
    """Pemilik boleh mengubah; petugas/admin boleh membaca semuanya."""

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if user.is_admin:
            return True
        if user.is_petugas:
            return request.method in SAFE_METHODS or obj.instansi_id == user.instansi_id
        return getattr(obj, "pelapor_id", None) == user.id
