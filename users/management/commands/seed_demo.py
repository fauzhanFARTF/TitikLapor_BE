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

        self.stdout.write(
            self.style.WARNING("Kata sandi seluruh akun demo: TitikLapor123!")
        )
