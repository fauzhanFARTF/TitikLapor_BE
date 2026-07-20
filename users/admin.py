from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from users.models import Instansi, User


@admin.register(Instansi)
class InstansiAdmin(admin.ModelAdmin):
    list_display = ("kode", "nama", "email_kontak", "is_active")
    search_fields = ("kode", "nama")
    list_filter = ("is_active",)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("-created_at",)
    list_display = ("email", "nama_lengkap", "role", "instansi", "is_active")
    list_filter = ("role", "is_active", "instansi")
    search_fields = ("email", "nama_lengkap")
    readonly_fields = ("created_at", "updated_at", "last_login")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profil", {"fields": ("nama_lengkap", "nomor_telepon", "foto")}),
        ("Peran", {"fields": ("role", "instansi")}),
        ("Izin", {"fields": ("is_active", "is_staff", "is_superuser", "groups")}),
        ("Waktu", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "nama_lengkap", "role", "password1", "password2"),
            },
        ),
    )
