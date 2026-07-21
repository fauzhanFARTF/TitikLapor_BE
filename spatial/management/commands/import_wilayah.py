"""Impor batas wilayah administratif dari berkas GeoJSON.

    python manage.py import_wilayah                       # berkas bawaan
    python manage.py import_wilayah --file batas.geojson  # berkas lain
    python manage.py import_wilayah --dry-run             # periksa tanpa menyimpan

Nama kolom properti dapat disesuaikan lewat opsi, sehingga command ini tidak
terikat pada satu sumber data saja.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from spatial.models import Wilayah

# Berkas bawaan: 29 kecamatan Kabupaten Tangerang (kode BPS 36.03.xx).
BERKAS_BAWAAN = (
    Path(__file__).resolve().parents[2] / "data" / "BATAS_KECAMATAN_AR.geojson"
)


class Command(BaseCommand):
    help = "Impor batas wilayah administratif (GeoJSON) ke tabel Wilayah."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=str(BERKAS_BAWAAN),
            help="Path berkas GeoJSON. Default: data kecamatan bawaan repo.",
        )
        parser.add_argument(
            "--tingkat",
            default=Wilayah.Tingkat.KECAMATAN,
            choices=Wilayah.Tingkat.values,
            help="Tingkat administratif fitur di dalam berkas.",
        )
        parser.add_argument(
            "--nama-field",
            default="KECAMATAN",
            help="Nama properti GeoJSON yang memuat nama wilayah.",
        )
        parser.add_argument(
            "--kode-field",
            default="KD_KCMTAN",
            help="Nama properti GeoJSON yang memuat kode wilayah.",
        )
        parser.add_argument(
            "--induk-nama",
            default="",
            help=(
                "Bila diisi, dibuat satu wilayah induk bertingkat KOTA hasil "
                "penggabungan seluruh poligon anak, mis. 'Kabupaten Tangerang'."
            ),
        )
        parser.add_argument(
            "--induk-kode",
            default="",
            help="Kode wilayah induk. Default: prefiks kode anak (mis. 36.03).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Periksa & laporkan tanpa menulis ke database.",
        )

    # ── Alur utama ───────────────────────────────────────────────────────────

    def handle(self, *args, **opsi):
        berkas = Path(opsi["file"])
        if not berkas.exists():
            raise CommandError(f"Berkas tidak ditemukan: {berkas}")

        try:
            data = json.loads(berkas.read_text())
        except json.JSONDecodeError as exc:
            raise CommandError(f"GeoJSON tidak valid: {exc}") from exc

        if data.get("type") != "FeatureCollection":
            raise CommandError("Berkas harus berupa FeatureCollection.")

        fitur = data.get("features", [])
        if not fitur:
            raise CommandError("FeatureCollection tidak memuat satu fitur pun.")

        self.stdout.write(f"Membaca {len(fitur)} fitur dari {berkas.name}")

        siap, dilewati = self._siapkan(fitur, opsi)

        for alasan in dilewati:
            self.stdout.write(self.style.WARNING(f"  dilewati: {alasan}"))

        if not siap:
            raise CommandError("Tidak ada fitur yang dapat diimpor.")

        if opsi["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    f"\n[dry-run] {len(siap)} wilayah siap diimpor, "
                    f"{len(dilewati)} dilewati. Tidak ada yang ditulis."
                )
            )
            self._tampilkan_contoh(siap)
            return

        baru, diperbarui = self._simpan(siap, opsi)
        induk = self._buat_induk(opsi) if opsi["induk_nama"] else None
        self._hitung_luas()

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSelesai — {baru} wilayah baru, {diperbarui} diperbarui"
                + (f", induk '{induk.nama}' dibuat" if induk else "")
            )
        )
        self._ringkasan(opsi["tingkat"])

    # ── Penyiapan & validasi ─────────────────────────────────────────────────

    def _siapkan(self, fitur: list, opsi: dict) -> tuple[list, list]:
        """Ubah fitur GeoJSON menjadi data siap simpan, sambil menyaring yang cacat."""

        nama_field, kode_field = opsi["nama_field"], opsi["kode_field"]
        siap, dilewati, kode_terlihat = [], [], set()

        for i, f in enumerate(fitur):
            props = f.get("properties") or {}
            nama = (props.get(nama_field) or "").strip()
            kode = (props.get(kode_field) or "").strip()

            if not nama or not kode:
                dilewati.append(
                    f"fitur #{i}: properti {nama_field}/{kode_field} kosong"
                )
                continue

            if kode in kode_terlihat:
                # Kode ganda berarti sumber datanya bermasalah — lebih baik
                # dilaporkan daripada diam-diam menimpa baris sebelumnya.
                dilewati.append(f"fitur #{i} ({nama}): kode {kode} duplikat")
                continue

            geom = self._baca_geometri(f.get("geometry"))
            if geom is None:
                dilewati.append(
                    f"fitur #{i} ({nama}): geometri tidak valid atau kosong"
                )
                continue

            kode_terlihat.add(kode)
            siap.append({"nama": self._rapikan_nama(nama), "kode": kode, "geom": geom})

        return siap, dilewati

    @staticmethod
    def _baca_geometri(geometry: dict | None) -> MultiPolygon | None:
        """Kembalikan MultiPolygon SRID 4326, atau None bila tidak layak pakai."""

        if not geometry:
            return None
        try:
            geom = GEOSGeometry(json.dumps(geometry), srid=4326)
        except Exception:  # noqa: BLE001 — sumber data eksternal, apa pun bisa terjadi
            return None

        # Kolom model bertipe MultiPolygon; Polygon tunggal dibungkus agar
        # berkas dari sumber lain tetap dapat dipakai.
        if geom.geom_type == "Polygon":
            geom = MultiPolygon(geom, srid=4326)
        elif geom.geom_type != "MultiPolygon":
            return None

        if geom.empty or not geom.valid:
            # buffer(0) adalah cara baku memperbaiki poligon yang bersilangan
            # sendiri — kerap muncul pada data batas hasil digitasi.
            geom = geom.buffer(0)
            if geom.geom_type == "Polygon":
                geom = MultiPolygon(geom, srid=4326)
            if geom.empty or geom.geom_type != "MultiPolygon":
                return None
            geom.srid = 4326

        return geom

    @staticmethod
    def _rapikan_nama(nama: str) -> str:
        """'PASAR KEMIS' → 'Pasar Kemis'. Data BPS ditulis kapital seluruhnya."""

        return " ".join(bagian.capitalize() for bagian in nama.split())

    # ── Penyimpanan ──────────────────────────────────────────────────────────

    @transaction.atomic
    def _simpan(self, siap: list, opsi: dict) -> tuple[int, int]:
        baru = diperbarui = 0

        for item in siap:
            _, dibuat = Wilayah.all_objects.update_or_create(
                kode=item["kode"],
                defaults={
                    "nama": item["nama"],
                    "tingkat": opsi["tingkat"],
                    "geom": item["geom"],
                    # Baris yang sebelumnya dihapus lunak dihidupkan kembali.
                    "is_deleted": False,
                    "deleted_at": None,
                },
            )
            baru += dibuat
            diperbarui += not dibuat

        return baru, diperbarui

    @transaction.atomic
    def _buat_induk(self, opsi: dict) -> Wilayah:
        """Bentuk wilayah induk dari gabungan seluruh poligon anak.

        Sumber data hanya memuat kecamatan, tanpa poligon kabupaten. Menggabung
        anak-anaknya memberi tingkat KOTA untuk peta choropleth tanpa perlu
        berkas tambahan.
        """

        anak = list(Wilayah.objects.filter(tingkat=opsi["tingkat"]))
        gabungan = anak[0].geom
        for w in anak[1:]:
            gabungan = gabungan.union(w.geom)

        if gabungan.geom_type == "Polygon":
            gabungan = MultiPolygon(gabungan, srid=4326)
        gabungan.srid = 4326

        kode = opsi["induk_kode"] or anak[0].kode.rsplit(".", 1)[0]
        induk, _ = Wilayah.all_objects.update_or_create(
            kode=kode,
            defaults={
                "nama": opsi["induk_nama"],
                "tingkat": Wilayah.Tingkat.KOTA,
                "geom": gabungan,
                "is_deleted": False,
                "deleted_at": None,
            },
        )

        Wilayah.objects.filter(tingkat=opsi["tingkat"]).update(induk=induk)
        return induk

    @staticmethod
    def _hitung_luas() -> None:
        """Isi luas_km2 lewat PostGIS.

        Perhitungan dilakukan pada tipe `geography` agar hasilnya luas
        sebenarnya di permukaan bumi — menghitung luas langsung dari koordinat
        derajat menghasilkan angka yang tidak berarti.
        """

        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE wilayah SET luas_km2 = ST_Area(geom::geography) / 1000000.0"
            )

    # ── Laporan ──────────────────────────────────────────────────────────────

    def _tampilkan_contoh(self, siap: list) -> None:
        self.stdout.write("\nContoh 5 pertama:")
        for item in siap[:5]:
            self.stdout.write(f"  {item['kode']}  {item['nama']}")

    def _ringkasan(self, tingkat: str) -> None:
        qs = Wilayah.objects.filter(tingkat=tingkat).order_by("-luas_km2")
        total = sum(w.luas_km2 or 0 for w in qs)

        self.stdout.write(f"\nTotal luas {tingkat.lower()}: {total:,.1f} km²")
        self.stdout.write("Tiga terluas:")
        for w in qs[:3]:
            self.stdout.write(f"  {w.nama:20} {w.luas_km2:8.2f} km²")
