"""Model pengguna & instansi penanggung jawab laporan."""

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from core.models import BaseModel, TimeStampedModel, UUIDModel
from users.managers import UserManager


class Instansi(BaseModel):
    """Dinas/OPD yang menangani kategori laporan tertentu."""

    nama = models.CharField(max_length=150, unique=True)
    kode = models.CharField(
        max_length=20,
        unique=True,
        help_text="Kode singkat instansi, mis. DPUPR.",
    )
    deskripsi = models.TextField(blank=True)
    email_kontak = models.EmailField(blank=True)
    telepon = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "instansi"
        verbose_name = "Instansi"
        verbose_name_plural = "Instansi"
        ordering = ["nama"]

    def __str__(self) -> str:
        return f"{self.kode} — {self.nama}"


class User(UUIDModel, TimeStampedModel, AbstractBaseUser, PermissionsMixin):
    """Pengguna aplikasi. Satu tabel untuk tiga peran, dibedakan kolom `role`."""

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrator"
        PETUGAS = "PETUGAS", "Petugas Instansi"
        WARGA = "WARGA", "Warga"

    email = models.EmailField(unique=True, db_index=True)
    nama_lengkap = models.CharField(max_length=150)
    nomor_telepon = models.CharField(max_length=30, blank=True)
    role = models.CharField(
        max_length=10, choices=Role.choices, default=Role.WARGA, db_index=True
    )
    # Wajib untuk PETUGAS; null untuk ADMIN & WARGA.
    instansi = models.ForeignKey(
        Instansi,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="petugas",
    )
    foto = models.ImageField(upload_to="avatar/%Y/%m/", null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nama_lengkap"]

    class Meta:
        db_table = "users"
        verbose_name = "Pengguna"
        verbose_name_plural = "Pengguna"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["role", "instansi"])]

    def __str__(self) -> str:
        return f"{self.nama_lengkap} <{self.email}>"

    # ── Helper peran (dipakai permission class & serializer) ─────────────────

    @property
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN

    @property
    def is_petugas(self) -> bool:
        return self.role == self.Role.PETUGAS

    @property
    def is_warga(self) -> bool:
        return self.role == self.Role.WARGA
