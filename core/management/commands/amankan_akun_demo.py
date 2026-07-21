"""Amankan akun demo sebelum instalasi dilepas ke publik.

    python manage.py amankan_akun_demo              # nonaktifkan (default)
    python manage.py amankan_akun_demo --acak-sandi # tetap aktif, sandi diacak
    python manage.py amankan_akun_demo --hapus      # hapus PERMANEN

Akun contoh dari `seed_demo` memakai kata sandi yang tertulis terbuka di
README. Berguna saat pengembangan, berbahaya begitu layanan dapat diakses
siapa saja.
"""

from __future__ import annotations

import secrets

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import User

SANDI_DEMO = "TitikLapor123!"


class Command(BaseCommand):
    help = "Nonaktifkan, acak sandi, atau hapus akun demo berkata sandi bawaan."

    def add_arguments(self, parser):
        kelompok = parser.add_mutually_exclusive_group()
        kelompok.add_argument(
            "--acak-sandi",
            action="store_true",
            help="Akun tetap aktif, kata sandinya diganti acak dan ditampilkan sekali.",
        )
        kelompok.add_argument(
            "--hapus",
            action="store_true",
            help=(
                "Hapus akun demo PERMANEN. Model User tidak memakai soft delete, "
                "jadi tindakan ini tidak dapat dibatalkan. Laporan yang pernah "
                "dibuat tetap tersimpan (relasi pelapor bersifat SET_NULL dan "
                "namanya sudah disalin ke kolom nama_pelapor)."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Tampilkan akun yang terdampak tanpa mengubah apa pun.",
        )

    @transaction.atomic
    def handle(self, *args, **opsi):
        # Cara satu-satunya mengenali akun demo adalah mencoba kata sandinya —
        # hash tidak dapat dibaca balik.
        demo = [u for u in User.objects.all() if u.check_password(SANDI_DEMO)]

        if not demo:
            self.stdout.write(
                self.style.SUCCESS("Tidak ada akun berkata sandi bawaan. Aman.")
            )
            return

        self.stdout.write(f"Ditemukan {len(demo)} akun berkata sandi bawaan:")
        for u in demo:
            self.stdout.write(f"  {u.email} ({u.role})")

        if opsi["dry_run"]:
            self.stdout.write(self.style.WARNING("\n[dry-run] Tidak ada yang diubah."))
            return

        if opsi["acak_sandi"]:
            self._acak_sandi(demo)
        elif opsi["hapus"]:
            self._hapus(demo)
        else:
            self._nonaktifkan(demo)

    # ── Tindakan ─────────────────────────────────────────────────────────────

    def _nonaktifkan(self, demo: list[User]) -> None:
        for u in demo:
            u.is_active = False
            u.save(update_fields=["is_active", "updated_at"])

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{len(demo)} akun dinonaktifkan — tidak dapat login lagi."
            )
        )
        self.stdout.write(
            "Aktifkan kembali lewat panel admin bila sewaktu-waktu diperlukan."
        )

    def _acak_sandi(self, demo: list[User]) -> None:
        self.stdout.write("\nKata sandi baru (ditampilkan sekali, catat sekarang):")
        for u in demo:
            sandi = secrets.token_urlsafe(16)
            u.set_password(sandi)
            u.save(update_fields=["password", "updated_at"])
            self.stdout.write(f"  {u.email:28} {sandi}")

        self.stdout.write(
            self.style.WARNING(
                "\nKata sandi ini tidak tersimpan di mana pun selain database "
                "(dalam bentuk hash) — tidak dapat ditampilkan ulang."
            )
        )

    def _hapus(self, demo: list[User]) -> None:
        # Model User tidak mewarisi SoftDeleteModel, jadi ini penghapusan
        # sungguhan. Laporan yang pernah dibuat tetap aman karena relasinya
        # SET_NULL dan nama pelapor sudah disalin saat laporan dibuat.
        for u in demo:
            u.delete()

        self.stdout.write(self.style.SUCCESS(f"\n{len(demo)} akun dihapus permanen."))
        self.stdout.write(
            "Laporan yang pernah dibuat tetap tersimpan beserta nama pelapornya."
        )
