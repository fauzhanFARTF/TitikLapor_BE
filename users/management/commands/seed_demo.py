"""Isi database dengan data contoh untuk demo & pengembangan lokal.

python manage.py seed_demo
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Instansi, User

INSTANSI_DEMO = [
    ("DPUPR", "Dinas Pekerjaan Umum dan Penataan Ruang", "Jalan, jembatan, drainase"),
    ("DLH", "Dinas Lingkungan Hidup", "Sampah, pencemaran, ruang terbuka hijau"),
    ("DISHUB", "Dinas Perhubungan", "Rambu, lampu lalu lintas, parkir"),
    ("DISKOMINFO", "Dinas Komunikasi dan Informatika", "Infrastruktur TIK publik"),
]

# (nama, slug, ikon Font Awesome, warna penanda peta, kode instansi, SLA hari)
KATEGORI_DEMO = [
    (
        "Jalan Rusak",
        "jalan-rusak",
        "fa-road-circle-exclamation",
        "#dc2626",
        "DPUPR",
        14,
    ),
    ("Drainase Tersumbat", "drainase", "fa-water", "#0891b2", "DPUPR", 7),
    ("Penerangan Jalan Mati", "penerangan", "fa-lightbulb", "#f59e0b", "DPUPR", 5),
    ("Sampah Menumpuk", "sampah", "fa-trash", "#16a34a", "DLH", 3),
    ("Pencemaran Lingkungan", "pencemaran", "fa-smog", "#7c3aed", "DLH", 10),
    ("Rambu & Marka Rusak", "rambu", "fa-traffic-light", "#0ea5e9", "DISHUB", 7),
    ("Parkir Liar", "parkir-liar", "fa-square-parking", "#ea580c", "DISHUB", 3),
]


class Command(BaseCommand):
    help = "Membuat instansi contoh serta akun admin, petugas, dan warga demo."

    @transaction.atomic
    def handle(self, *args, **options):
        for kode, nama, deskripsi in INSTANSI_DEMO:
            Instansi.objects.get_or_create(
                kode=kode, defaults={"nama": nama, "deskripsi": deskripsi}
            )
        self.stdout.write(self.style.SUCCESS(f"{len(INSTANSI_DEMO)} instansi siap."))

        akun = [
            ("admin@titiklapor.id", "Administrator", User.Role.ADMIN, None),
            ("petugas@titiklapor.id", "Petugas DPUPR", User.Role.PETUGAS, "DPUPR"),
            ("warga@titiklapor.id", "Warga Demo", User.Role.WARGA, None),
        ]

        for email, nama, role, kode_instansi in akun:
            if User.objects.filter(email=email).exists():
                continue
            User.objects.create_user(
                email=email,
                password="TitikLapor123!",
                nama_lengkap=nama,
                role=role,
                instansi=Instansi.objects.filter(kode=kode_instansi).first(),
                is_staff=role == User.Role.ADMIN,
                is_superuser=role == User.Role.ADMIN,
            )
            self.stdout.write(self.style.SUCCESS(f"Akun {email} dibuat."))

        self._seed_kategori()

        self.stdout.write(
            self.style.WARNING("Kata sandi seluruh akun demo: TitikLapor123!")
        )

    def _seed_kategori(self) -> None:
        # Diimpor di dalam method agar command tetap bisa dipakai walau app
        # reports dinonaktifkan pada instalasi minimal.
        from reports.models import Kategori

        for nama, slug, ikon, warna, kode_instansi, sla in KATEGORI_DEMO:
            Kategori.objects.get_or_create(
                slug=slug,
                defaults={
                    "nama": nama,
                    "ikon": ikon,
                    "warna": warna,
                    "sla_hari": sla,
                    "instansi_default": Instansi.objects.filter(
                        kode=kode_instansi
                    ).first(),
                },
            )
        self.stdout.write(self.style.SUCCESS(f"{len(KATEGORI_DEMO)} kategori siap."))
