"""Pengujian impor batas wilayah & reverse-lookup administratif."""

import json

import pytest
from django.contrib.gis.geos import Point
from django.core.management import CommandError, call_command

from spatial.models import Wilayah
from spatial.services import spatial_service

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _kotak(x0: float, y0: float, x1: float, y1: float) -> dict:
    """Poligon persegi sederhana — cukup untuk menguji alur impor."""

    return {
        "type": "Polygon",
        "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]],
    }


def _multi(x0: float, y0: float, x1: float, y1: float) -> dict:
    return {
        "type": "MultiPolygon",
        "coordinates": [_kotak(x0, y0, x1, y1)["coordinates"]],
    }


def _tulis(tmp_path, fitur: list, nama="uji.geojson"):
    berkas = tmp_path / nama
    berkas.write_text(json.dumps({"type": "FeatureCollection", "features": fitur}))
    return str(berkas)


def _fitur(nama: str, kode: str, geom: dict) -> dict:
    return {
        "type": "Feature",
        "properties": {"KECAMATAN": nama, "KD_KCMTAN": kode},
        "geometry": geom,
    }


# ── Alur impor ──────────────────────────────────────────────────────────────


def test_impor_membuat_wilayah(tmp_path):
    berkas = _tulis(
        tmp_path,
        [
            _fitur("BALARAJA", "36.03.01", _multi(106.4, -6.2, 106.5, -6.1)),
            _fitur("JAYANTI", "36.03.02", _multi(106.5, -6.2, 106.6, -6.1)),
        ],
    )
    call_command("import_wilayah", file=berkas, verbosity=0)

    assert Wilayah.objects.count() == 2
    # Nama BPS ditulis kapital seluruhnya; impor merapikannya.
    assert Wilayah.objects.get(kode="36.03.01").nama == "Balaraja"


def test_impor_bersifat_idempoten(tmp_path):
    """Menjalankan ulang harus memperbarui, bukan menggandakan."""

    berkas = _tulis(
        tmp_path, [_fitur("BALARAJA", "36.03.01", _multi(106.4, -6.2, 106.5, -6.1))]
    )

    call_command("import_wilayah", file=berkas, verbosity=0)
    call_command("import_wilayah", file=berkas, verbosity=0)

    assert Wilayah.objects.filter(kode="36.03.01").count() == 1


def test_poligon_tunggal_dibungkus_jadi_multipolygon(tmp_path):
    """Kolom model bertipe MultiPolygon; sumber lain kerap memakai Polygon."""

    berkas = _tulis(
        tmp_path, [_fitur("CISOKA", "36.03.05", _kotak(106.4, -6.2, 106.5, -6.1))]
    )
    call_command("import_wilayah", file=berkas, verbosity=0)

    assert Wilayah.objects.get(kode="36.03.05").geom.geom_type == "MultiPolygon"


def test_luas_dihitung_dalam_kilometer_persegi(tmp_path):
    """Luas dihitung pada tipe geography, bukan dari koordinat derajat."""

    # Kotak 0,1° × 0,1° di sekitar khatulistiwa ≈ 11 km × 11 km ≈ 120 km².
    berkas = _tulis(
        tmp_path, [_fitur("BALARAJA", "36.03.01", _multi(106.4, -6.2, 106.5, -6.1))]
    )
    call_command("import_wilayah", file=berkas, verbosity=0)

    luas = Wilayah.objects.get(kode="36.03.01").luas_km2
    assert 100 < luas < 150, f"luas tidak masuk akal: {luas}"


def test_fitur_tanpa_nama_atau_kode_dilewati(tmp_path):
    berkas = _tulis(
        tmp_path,
        [
            _fitur("BALARAJA", "36.03.01", _multi(106.4, -6.2, 106.5, -6.1)),
            _fitur("", "36.03.02", _multi(106.5, -6.2, 106.6, -6.1)),
            _fitur("KRESEK", "", _multi(106.6, -6.2, 106.7, -6.1)),
        ],
    )
    call_command("import_wilayah", file=berkas, verbosity=0)

    assert Wilayah.objects.count() == 1


def test_kode_duplikat_dilewati_bukan_menimpa(tmp_path):
    """Kode ganda menandakan sumber data bermasalah — jangan diam-diam ditimpa."""

    berkas = _tulis(
        tmp_path,
        [
            _fitur("BALARAJA", "36.03.01", _multi(106.4, -6.2, 106.5, -6.1)),
            _fitur("NAMA LAIN", "36.03.01", _multi(106.5, -6.2, 106.6, -6.1)),
        ],
    )
    call_command("import_wilayah", file=berkas, verbosity=0)

    assert Wilayah.objects.count() == 1
    assert Wilayah.objects.get(kode="36.03.01").nama == "Balaraja"


def test_dry_run_tidak_menulis_apa_pun(tmp_path):
    berkas = _tulis(
        tmp_path, [_fitur("BALARAJA", "36.03.01", _multi(106.4, -6.2, 106.5, -6.1))]
    )
    call_command("import_wilayah", file=berkas, dry_run=True, verbosity=0)

    assert Wilayah.objects.count() == 0


def test_berkas_tidak_ada_memberi_pesan_jelas():
    with pytest.raises(CommandError, match="tidak ditemukan"):
        call_command("import_wilayah", file="/tmp/berkas-yang-tidak-ada.geojson")


def test_geojson_rusak_memberi_pesan_jelas(tmp_path):
    berkas = tmp_path / "rusak.geojson"
    berkas.write_text("{ ini bukan json }")

    with pytest.raises(CommandError, match="tidak valid"):
        call_command("import_wilayah", file=str(berkas))


def test_induk_dibentuk_dari_gabungan_anak(tmp_path):
    """Sumber data hanya memuat kecamatan; induk KOTA dibentuk dari gabungannya."""

    berkas = _tulis(
        tmp_path,
        [
            _fitur("BALARAJA", "36.03.01", _multi(106.4, -6.2, 106.5, -6.1)),
            _fitur("JAYANTI", "36.03.02", _multi(106.5, -6.2, 106.6, -6.1)),
        ],
    )
    call_command(
        "import_wilayah", file=berkas, induk_nama="Kabupaten Tangerang", verbosity=0
    )

    induk = Wilayah.objects.get(tingkat=Wilayah.Tingkat.KOTA)
    assert induk.nama == "Kabupaten Tangerang"
    assert induk.kode == "36.03"  # prefiks kode anak
    assert Wilayah.objects.filter(induk=induk).count() == 2
    # Gabungan dua kotak bersebelahan harus mencakup keduanya.
    assert induk.geom.contains(Point(106.45, -6.15, srid=4326))
    assert induk.geom.contains(Point(106.55, -6.15, srid=4326))


# ── Reverse lookup ──────────────────────────────────────────────────────────


def test_reverse_lookup_mengembalikan_wilayah_paling_spesifik(tmp_path):
    """Regresi: sebelumnya `order_by("-tingkat")` justru mengembalikan KOTA.

    Urutan alfabetis tidak mencerminkan kekhususan — KECAMATAN < KELURAHAN <
    KOTA — sehingga titik di dalam kecamatan malah dijawab dengan nama
    kabupatennya.
    """

    berkas = _tulis(
        tmp_path, [_fitur("TIGARAKSA", "36.03.03", _multi(106.4, -6.3, 106.6, -6.1))]
    )
    call_command(
        "import_wilayah", file=berkas, induk_nama="Kabupaten Tangerang", verbosity=0
    )

    hasil = spatial_service.wilayah_dari_titik(-6.2, 106.5)

    assert hasil is not None
    assert hasil["tingkat"] == Wilayah.Tingkat.KECAMATAN
    assert hasil["nama"] == "Tigaraksa"
    assert hasil["induk"] == "Kabupaten Tangerang"


def test_reverse_lookup_di_luar_cakupan_mengembalikan_none(tmp_path):
    berkas = _tulis(
        tmp_path, [_fitur("BALARAJA", "36.03.01", _multi(106.4, -6.2, 106.5, -6.1))]
    )
    call_command("import_wilayah", file=berkas, verbosity=0)

    assert spatial_service.wilayah_dari_titik(-6.9, 107.9) is None


# ── Agregasi choropleth ─────────────────────────────────────────────────────


def test_agregasi_menghitung_laporan_per_wilayah(tmp_path, kategori, warga):
    from django.core.cache import cache

    from reports.services import laporan_service

    cache.clear()
    berkas = _tulis(
        tmp_path,
        [
            _fitur("BALARAJA", "36.03.01", _multi(106.4, -6.2, 106.5, -6.1)),
            _fitur("JAYANTI", "36.03.02", _multi(106.5, -6.2, 106.6, -6.1)),
        ],
    )
    call_command("import_wilayah", file=berkas, verbosity=0)

    # Dua laporan di Balaraja, satu di Jayanti.
    for lat, lon in [(-6.15, 106.45), (-6.16, 106.46), (-6.15, 106.55)]:
        laporan_service.buat_laporan(
            pelapor=warga,
            judul="Laporan uji agregasi",
            deskripsi="Deskripsi laporan uji agregasi wilayah.",
            kategori_id=kategori.id,
            latitude=lat,
            longitude=lon,
        )

    hasil = {w["nama"]: w for w in spatial_service.agregasi_per_wilayah("KECAMATAN")}

    assert hasil["Balaraja"]["total_laporan"] == 2
    assert hasil["Jayanti"]["total_laporan"] == 1
    # Kepadatan hanya bisa dihitung kalau luas sudah terisi saat impor.
    assert hasil["Balaraja"]["kepadatan_per_km2"] is not None
    cache.clear()
