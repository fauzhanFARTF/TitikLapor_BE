"""Model laporan warga beserta kategori, riwayat status, dan lampiran."""

from django.contrib.gis.db import models as gis_models
from django.db import models

from core.models import BaseModel
from users.models import Instansi, User


class Kategori(BaseModel):
    """Jenis masalah yang bisa dilaporkan; menentukan instansi tujuan."""

    nama = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True)
    ikon = models.CharField(
        max_length=50,
        default="fa-triangle-exclamation",
        help_text="Nama kelas ikon Font Awesome untuk penanda peta.",
    )
    warna = models.CharField(
        max_length=7, default="#dc2626", help_text="Warna hex penanda peta."
    )
    # Instansi default penerima laporan kategori ini — bisa dialihkan admin.
    instansi_default = models.ForeignKey(
        Instansi,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kategori",
    )
    sla_hari = models.PositiveSmallIntegerField(
        default=7, help_text="Target penyelesaian dalam hari kerja."
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "kategori"
        verbose_name = "Kategori"
        verbose_name_plural = "Kategori"
        ordering = ["nama"]

    def __str__(self) -> str:
        return self.nama


class Laporan(BaseModel):
    """Satu titik laporan warga di peta."""

    class Status(models.TextChoices):
        BARU = "BARU", "Baru"
        DIVERIFIKASI = "DIVERIFIKASI", "Diverifikasi"
        DIPROSES = "DIPROSES", "Sedang Diproses"
        SELESAI = "SELESAI", "Selesai"
        DITOLAK = "DITOLAK", "Ditolak"

    class Prioritas(models.TextChoices):
        RENDAH = "RENDAH", "Rendah"
        SEDANG = "SEDANG", "Sedang"
        TINGGI = "TINGGI", "Tinggi"

    nomor_tiket = models.CharField(max_length=20, unique=True, db_index=True)
    judul = models.CharField(max_length=200)
    deskripsi = models.TextField()

    kategori = models.ForeignKey(
        Kategori, on_delete=models.PROTECT, related_name="laporan"
    )
    instansi = models.ForeignKey(
        Instansi,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="laporan",
    )

    # ── Geospasial ────────────────────────────────────────────────────────────
    # SRID 4326 (WGS84) — sama dengan output GPS browser, tanpa transformasi.
    lokasi = gis_models.PointField(srid=4326, geography=True, db_index=True)
    alamat = models.CharField(max_length=255, blank=True)
    kelurahan = models.CharField(max_length=100, blank=True, db_index=True)
    kecamatan = models.CharField(max_length=100, blank=True, db_index=True)

    foto = models.ImageField(upload_to="laporan/%Y/%m/", null=True, blank=True)

    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.BARU, db_index=True
    )
    prioritas = models.CharField(
        max_length=10, choices=Prioritas.choices, default=Prioritas.SEDANG
    )

    # Pelapor di-SET_NULL agar laporan tetap ada saat akun dihapus; nama
    # disalin ke snapshot supaya riwayat tetap terbaca.
    pelapor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="laporan"
    )
    nama_pelapor = models.CharField(max_length=150, blank=True)
    is_anonim = models.BooleanField(default=False)

    petugas = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="laporan_ditangani",
        limit_choices_to={"role": User.Role.PETUGAS},
    )

    # Cap waktu transisi — dipakai menghitung durasi respons & kepatuhan SLA.
    diverifikasi_at = models.DateTimeField(null=True, blank=True)
    diproses_at = models.DateTimeField(null=True, blank=True)
    selesai_at = models.DateTimeField(null=True, blank=True)

    catatan_penyelesaian = models.TextField(blank=True)
    foto_penyelesaian = models.ImageField(
        upload_to="penyelesaian/%Y/%m/", null=True, blank=True
    )

    jumlah_dukungan = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "laporan"
        verbose_name = "Laporan"
        verbose_name_plural = "Laporan"
        ordering = ["-created_at"]
        indexes = [
            # Pola query terbanyak: filter status + kategori diurutkan terbaru.
            models.Index(fields=["status", "kategori", "-created_at"]),
            models.Index(fields=["instansi", "status"]),
            models.Index(fields=["pelapor", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.nomor_tiket} — {self.judul}"

    @property
    def latitude(self) -> float:
        return self.lokasi.y

    @property
    def longitude(self) -> float:
        return self.lokasi.x


class RiwayatStatus(BaseModel):
    """Jejak audit setiap perubahan status laporan."""

    laporan = models.ForeignKey(
        Laporan, on_delete=models.CASCADE, related_name="riwayat"
    )
    status_lama = models.CharField(max_length=15, blank=True)
    status_baru = models.CharField(max_length=15)
    catatan = models.TextField(blank=True)
    oleh = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    nama_oleh = models.CharField(max_length=150, blank=True)

    class Meta:
        db_table = "riwayat_status"
        verbose_name = "Riwayat Status"
        verbose_name_plural = "Riwayat Status"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.laporan_id}: {self.status_lama or '-'} → {self.status_baru}"


class Dukungan(BaseModel):
    """Satu warga mendukung ('saya juga mengalami') satu laporan."""

    laporan = models.ForeignKey(
        Laporan, on_delete=models.CASCADE, related_name="dukungan"
    )
    warga = models.ForeignKey(User, on_delete=models.CASCADE, related_name="dukungan")

    class Meta:
        db_table = "dukungan"
        verbose_name = "Dukungan"
        verbose_name_plural = "Dukungan"
        constraints = [
            models.UniqueConstraint(
                fields=["laporan", "warga"], name="uniq_dukungan_per_warga"
            )
        ]


class Tanggapan(BaseModel):
    """Percakapan antara pelapor dan petugas pada satu laporan."""

    laporan = models.ForeignKey(
        Laporan, on_delete=models.CASCADE, related_name="tanggapan"
    )
    penulis = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="tanggapan"
    )
    nama_penulis = models.CharField(max_length=150, blank=True)
    peran_penulis = models.CharField(max_length=10, blank=True)
    isi = models.TextField()
    # Catatan internal hanya terlihat oleh petugas & admin.
    is_internal = models.BooleanField(default=False)

    class Meta:
        db_table = "tanggapan"
        verbose_name = "Tanggapan"
        verbose_name_plural = "Tanggapan"
        ordering = ["created_at"]
