"""Periksa kesiapan instalasi sebelum dilepas ke publik.

    python manage.py cek_kesiapan          # laporan lengkap
    python manage.py cek_kesiapan --ketat  # keluar kode 1 bila ada peringatan

`manage.py check --deploy` bawaan Django sudah memeriksa setelan keamanan
umum. Command ini melengkapinya dengan hal-hal yang khusus aplikasi ini:
akun demo yang masih hidup, rate limit yang tidak andal tanpa Redis, data
wilayah yang belum diimpor, dan penyimpanan media yang bersifat ephemeral.

Kode keluar: 0 bila aman, 1 bila ada masalah (atau peringatan pada --ketat).
"""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.core.management.base import BaseCommand

# Kata sandi yang tertulis terbuka di README — akun yang memakainya tidak
# boleh ikut terbawa ke lingkungan publik.
SANDI_DEMO = "TitikLapor123!"

MASALAH, PERINGATAN, AMAN = "MASALAH", "PERINGATAN", "AMAN"


@dataclass
class Temuan:
    tingkat: str
    judul: str
    pesan: str
    tindakan: str = ""


class Command(BaseCommand):
    help = "Periksa kesiapan instalasi untuk dilepas ke publik."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ketat",
            action="store_true",
            help="Perlakukan peringatan sebagai kegagalan (untuk dipakai di CI).",
        )

    def handle(self, *args, **opsi):
        temuan: list[Temuan] = []
        for pemeriksa in (
            self._cek_debug,
            self._cek_secret_key,
            self._cek_allowed_hosts,
            self._cek_https,
            self._cek_csp,
            self._cek_cors,
            self._cek_cache,
            self._cek_media,
            self._cek_akun_demo,
            self._cek_data_wilayah,
            self._cek_kategori,
        ):
            hasil = pemeriksa()
            if hasil:
                temuan.append(hasil)

        self._laporkan(temuan)

        masalah = [t for t in temuan if t.tingkat == MASALAH]
        peringatan = [t for t in temuan if t.tingkat == PERINGATAN]

        if masalah or (opsi["ketat"] and peringatan):
            raise SystemExit(1)

    # ── Konfigurasi inti ─────────────────────────────────────────────────────

    def _cek_debug(self) -> Temuan | None:
        if settings.DEBUG:
            return Temuan(
                MASALAH,
                "DEBUG aktif",
                "Halaman error akan membocorkan traceback, setelan, dan kueri SQL.",
                "Jalankan dengan DJANGO_ENV=production.",
            )
        return Temuan(AMAN, "DEBUG", "Nonaktif.")

    def _cek_secret_key(self) -> Temuan | None:
        kunci = settings.SECRET_KEY
        if "dev-only" in kunci or "ganti" in kunci.lower():
            return Temuan(
                MASALAH,
                "SECRET_KEY masih bawaan",
                "Kunci contoh dari repo dipakai — tanda tangan sesi & token dapat dipalsukan.",
                'Isi SECRET_KEY dengan: python -c "import secrets;print(secrets.token_urlsafe(64))"',
            )
        if len(kunci) < 50:
            return Temuan(
                PERINGATAN,
                "SECRET_KEY pendek",
                f"Panjangnya {len(kunci)} karakter; disarankan minimal 50.",
                "Ganti dengan kunci acak yang lebih panjang.",
            )
        return Temuan(
            AMAN, "SECRET_KEY", f"Panjang {len(kunci)} karakter, bukan bawaan."
        )

    def _cek_allowed_hosts(self) -> Temuan | None:
        hosts = settings.ALLOWED_HOSTS
        if not hosts:
            return Temuan(
                MASALAH,
                "ALLOWED_HOSTS kosong",
                "Django akan menolak seluruh permintaan di luar mode DEBUG.",
                "Isi HOSTS dengan domain sebenarnya, dipisah koma.",
            )
        if "*" in hosts:
            return Temuan(
                PERINGATAN,
                "ALLOWED_HOSTS memakai wildcard",
                "Membuka celah serangan Host header (mis. tautan reset sandi palsu).",
                "Ganti '*' dengan daftar domain yang sebenarnya.",
            )
        return Temuan(AMAN, "ALLOWED_HOSTS", ", ".join(hosts))

    def _cek_https(self) -> Temuan | None:
        if not getattr(settings, "SECURE_SSL_REDIRECT", False):
            return Temuan(
                MASALAH,
                "Pengalihan HTTPS mati",
                "HSTS ikut mati, dan kredensial dapat dikirim lewat HTTP polos.",
                "Set SECURE_SSL_REDIRECT=True.",
            )
        if not getattr(settings, "SECURE_HSTS_SECONDS", 0):
            return Temuan(
                PERINGATAN,
                "HSTS mati",
                "Header Strict-Transport-Security tidak dikirim.",
            )
        return Temuan(
            AMAN,
            "HTTPS & HSTS",
            f"Redirect aktif, HSTS {settings.SECURE_HSTS_SECONDS} detik.",
        )

    def _cek_csp(self) -> Temuan | None:
        if getattr(settings, "CSP_REPORT_ONLY", False):
            return Temuan(
                PERINGATAN,
                "CSP hanya report-only",
                "Pelanggaran dicatat tetapi tidak diblokir.",
                "Set CSP_REPORT_ONLY=False setelah yakin tidak ada yang rusak.",
            )
        return Temuan(AMAN, "CSP", "Ditegakkan (bukan report-only).")

    def _cek_cors(self) -> Temuan | None:
        origins = getattr(settings, "CORS_ALLOWED_ORIGINS", [])
        lokal = [o for o in origins if "localhost" in o or "127.0.0.1" in o]
        if not origins:
            return Temuan(
                PERINGATAN,
                "CORS_ORIGINS kosong",
                "Frontend di domain lain tidak akan bisa memanggil API.",
                "Isi CORS_ORIGINS dengan domain frontend.",
            )
        if lokal:
            return Temuan(
                PERINGATAN,
                "CORS masih memuat origin lokal",
                f"Origin pengembangan ikut terbawa: {', '.join(lokal)}",
                "Buang origin localhost dari CORS_ORIGINS di produksi.",
            )
        return Temuan(AMAN, "CORS", ", ".join(origins))

    # ── Ketergantungan runtime ───────────────────────────────────────────────

    def _cek_cache(self) -> Temuan | None:
        backend = settings.CACHES["default"]["BACKEND"]
        if "locmem" in backend.lower():
            return Temuan(
                PERINGATAN,
                "Cache memori lokal",
                "Penghitung rate limit login tersimpan per-proses. Dengan beberapa "
                "worker, batasnya berlipat dan tidak dapat diandalkan.",
                "Isi REDIS_URL.",
            )
        return Temuan(AMAN, "Cache", backend.rsplit(".", 1)[-1])

    def _cek_media(self) -> Temuan | None:
        if not getattr(settings, "USE_SUPABASE_STORAGE", False):
            return Temuan(
                PERINGATAN,
                "Media disimpan di filesystem",
                "Pada platform dengan filesystem ephemeral (HF Spaces, Fly.io), "
                "foto laporan warga hilang setiap container di-restart.",
                "Set USE_SUPABASE_STORAGE=True beserta kredensial S3-nya.",
            )
        return Temuan(AMAN, "Penyimpanan media", "Supabase Storage (object storage).")

    # ── Isi database ─────────────────────────────────────────────────────────

    def _cek_akun_demo(self) -> Temuan | None:
        from users.models import User

        rentan = [
            u.email
            for u in User.objects.filter(is_active=True)
            if u.check_password(SANDI_DEMO)
        ]
        if rentan:
            return Temuan(
                MASALAH,
                "Akun demo masih aktif",
                "Kata sandinya tertulis terbuka di README: " + ", ".join(rentan),
                "Jalankan: python manage.py amankan_akun_demo",
            )
        # Akun nonaktif sengaja tidak dihitung: kata sandinya mungkin masih
        # bawaan, tetapi tidak dapat dipakai login.
        return Temuan(
            AMAN, "Akun demo", "Tidak ada akun AKTIF yang memakai kata sandi bawaan."
        )

    def _cek_data_wilayah(self) -> Temuan | None:
        from spatial.models import Wilayah

        jumlah = Wilayah.objects.count()
        if not jumlah:
            return Temuan(
                PERINGATAN,
                "Data batas wilayah kosong",
                "Halaman Analitik Spasial akan kosong dan pengisian "
                "kelurahan/kecamatan otomatis tidak berfungsi.",
                'Jalankan: python manage.py import_wilayah --induk-nama "..."',
            )
        return Temuan(AMAN, "Data wilayah", f"{jumlah} wilayah terimpor.")

    def _cek_kategori(self) -> Temuan | None:
        from reports.models import Kategori

        tanpa_instansi = Kategori.objects.filter(
            is_active=True, instansi_default__isnull=True
        ).count()
        if not Kategori.objects.filter(is_active=True).exists():
            return Temuan(
                MASALAH,
                "Tidak ada kategori aktif",
                "Warga tidak akan bisa mengirim laporan sama sekali.",
                "Jalankan: python manage.py seed_demo, atau buat lewat panel admin.",
            )
        if tanpa_instansi:
            return Temuan(
                PERINGATAN,
                "Kategori tanpa instansi tujuan",
                f"{tanpa_instansi} kategori aktif belum dipetakan ke instansi mana pun, "
                "sehingga laporannya tidak akan masuk antrean siapa pun.",
                "Petakan lewat halaman Kategori di panel admin.",
            )
        return Temuan(
            AMAN, "Kategori", "Seluruh kategori aktif sudah punya instansi tujuan."
        )

    # ── Laporan ──────────────────────────────────────────────────────────────

    def _laporkan(self, temuan: list[Temuan]) -> None:
        gaya = {
            MASALAH: (self.style.ERROR, "✗"),
            PERINGATAN: (self.style.WARNING, "!"),
            AMAN: (self.style.SUCCESS, "✓"),
        }

        self.stdout.write("\nPemeriksaan kesiapan produksi")
        self.stdout.write("─" * 68)

        for t in temuan:
            warna, tanda = gaya[t.tingkat]
            self.stdout.write(warna(f"  {tanda} {t.judul}"))
            self.stdout.write(f"      {t.pesan}")
            if t.tindakan:
                self.stdout.write(f"      → {t.tindakan}")

        self.stdout.write("─" * 68)

        n_masalah = sum(t.tingkat == MASALAH for t in temuan)
        n_peringatan = sum(t.tingkat == PERINGATAN for t in temuan)

        if n_masalah:
            self.stdout.write(
                self.style.ERROR(
                    f"{n_masalah} masalah harus diperbaiki sebelum dilepas ke publik."
                )
            )
        elif n_peringatan:
            self.stdout.write(
                self.style.WARNING(f"{n_peringatan} peringatan — tinjau sebelum rilis.")
            )
        else:
            self.stdout.write(self.style.SUCCESS("Semua pemeriksaan lulus."))
        self.stdout.write("")
