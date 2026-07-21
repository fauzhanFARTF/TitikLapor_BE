---
title: Titik Lapor API
emoji: 📍
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# Titik Lapor — Backend

[![CI](https://github.com/fauzhanFARTF/TitikLapor_BE/actions/workflows/ci.yml/badge.svg)](https://github.com/fauzhanFARTF/TitikLapor_BE/actions/workflows/ci.yml)

REST API untuk platform pelaporan masalah publik berbasis peta. Dibangun dengan
**Django 6 + DRF + GeoDjango/PostGIS**, memakai arsitektur berlapis
(model → repository → service → API) sehingga aturan bisnis dapat diuji tanpa
menyentuh HTTP.

> Frontend-nya ada di repositori terpisah: **TitikLapor_FE** (Vue 3 + Vite).

---

## Daftar Isi

- [Arsitektur](#arsitektur)
- [Prasyarat](#prasyarat)
- [Menjalankan Secara Lokal](#menjalankan-secara-lokal)
- [Variabel Lingkungan](#variabel-lingkungan)
- [Model Domain](#model-domain)
- [Data Batas Wilayah](#data-batas-wilayah)
- [Peran & Otorisasi](#peran--otorisasi)
- [Alur Status Laporan](#alur-status-laporan)
- [Daftar Endpoint](#daftar-endpoint)
- [Fitur Spasial](#fitur-spasial)
- [Header Keamanan](#header-keamanan)
- [Pembatasan Laju & Sesi](#pembatasan-laju--sesi)
- [Pengujian](#pengujian)
- [Integrasi Berkelanjutan](#integrasi-berkelanjutan)
- [Kesiapan Produksi](#kesiapan-produksi)
- [Deployment](#deployment)
- [Alur Kerja Git](#alur-kerja-git)

---

## Arsitektur

```
TitikLapor_BE/
├── config/
│   ├── settings/
│   │   ├── base.py          # setting bersama
│   │   ├── development.py   # DEBUG, CSP report-only, cache lokal
│   │   └── production.py    # HTTPS, HSTS, WhiteNoise, Redis
│   ├── urls.py  wsgi.py  asgi.py
│
├── core/                    # fondasi lintas app
│   ├── models.py            # BaseModel = UUID + timestamp + soft delete
│   ├── managers.py          # SoftDeleteManager / QuerySet
│   ├── exceptions.py        # DomainError, InvalidStateTransition, …
│   ├── exception_handler.py # amplop error seragam
│   ├── mixins.py            # EnvelopeResponseMixin
│   ├── middleware/
│   │   └── security_headers.py   # CSP, Permissions-Policy, COOP/CORP
│   └── utils/               # responses, pagination
│
├── users/                   # pengguna & instansi
│   ├── models.py            # User (email login, 3 peran), Instansi
│   ├── permissions.py       # IsAdmin / IsPetugas / IsWarga
│   ├── services/            # auth_service — aturan registrasi & login
│   └── api/                 # serializers, views
│
├── reports/                 # inti aplikasi
│   ├── models.py            # Laporan (PointField), Kategori, RiwayatStatus,
│   │                        #   Dukungan, Tanggapan
│   ├── repositories/        # seluruh query & agregasi (termasuk spasial)
│   ├── services/            # state machine status, penomoran tiket, otorisasi
│   └── api/                 # serializers (termasuk GeoJSON), filters, views
│
├── spatial/                 # analisis geospasial
│   ├── models.py            # Wilayah (MultiPolygon), Fasilitas (Point)
│   ├── adapters/            # RoutingAdapter: naive & OSRM
│   ├── services/            # agregasi choropleth, heatmap, radius, rute
│   └── api/
│
└── tests/
    ├── unit/                # tanpa/ringan database
    └── integration/         # alur API lengkap
```

**Kenapa berlapis?** View hanya menerjemahkan HTTP; keputusan bisnis (siapa
boleh mengubah status apa, laporan mana yang boleh dilihat) tinggal di
`services/`, dan seluruh akses data terkumpul di `repositories/`. Akibatnya
aturan seperti "petugas hanya melihat laporan instansinya" ditegakkan satu kali
dan otomatis berlaku di semua endpoint.

---

## Prasyarat

| Kebutuhan | Versi | Catatan |
|---|---|---|
| Python | 3.12+ | Diuji di 3.12 (Docker) dan 3.14 (lokal) |
| PostgreSQL + PostGIS | 15+ / 3.4+ | Atau Supabase (PostGIS tinggal diaktifkan) |
| GDAL, GEOS, PROJ | terbaru | Wajib untuk GeoDjango |
| Redis | 7+ | Opsional — cache analisis spasial |

macOS:

```bash
brew install postgresql@17 postgis gdal geos proj
brew services start postgresql@17
```

Debian/Ubuntu:

```bash
sudo apt install -y postgresql postgresql-17-postgis-3 gdal-bin libgdal-dev libgeos-dev libproj-dev
```

---

## Menjalankan Secara Lokal

```bash
git clone <url-repo> TitikLapor_BE && cd TitikLapor_BE

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements/development.txt

cp .env.example .env      # lalu sesuaikan kredensial database

# Siapkan database + ekstensi PostGIS
createdb titiklapor
psql -d titiklapor -c "CREATE EXTENSION IF NOT EXISTS postgis;"

python manage.py migrate
python manage.py seed_demo        # instansi, kategori, & 3 akun contoh
python manage.py import_wilayah --induk-nama "Kabupaten Tangerang"
python manage.py runserver
```

API tersedia di `http://localhost:8000/api/v1/`.

**Akun demo** (kata sandi seragam `TitikLapor123!`):

| Email | Peran |
|---|---|
| `admin@titiklapor.id` | Administrator |
| `petugas@titiklapor.id` | Petugas DPUPR |
| `warga@titiklapor.id` | Warga |

> **macOS + Homebrew:** GeoDjango sering gagal menemukan GDAL/GEOS. Tambahkan
> di `.env`:
> ```
> GDAL_LIBRARY_PATH=/opt/homebrew/lib/libgdal.dylib
> GEOS_LIBRARY_PATH=/opt/homebrew/lib/libgeos_c.dylib
> ```

Alternatif tanpa memasang apa pun selain Docker:

```bash
docker compose up -d      # PostGIS 3.5 + Redis + API
```

---

## Variabel Lingkungan

Lihat `.env.example` untuk daftar lengkap. Yang paling sering diubah:

| Variabel | Default | Keterangan |
|---|---|---|
| `DJANGO_ENV` | `development` | Memilih modul setting yang dimuat |
| `SECRET_KEY` | — | **Wajib diisi di produksi** |
| `HOSTS` | kosong | `ALLOWED_HOSTS`, dipisah koma |
| `DB_*` | lokal | Kredensial Postgres/Supabase |
| `DB_SSLMODE` | `prefer` | Set `require` untuk Supabase/Neon/RDS |
| `CORS_ORIGINS` | `http://localhost:5173` | Origin frontend yang diizinkan |
| `SECURE_SSL_REDIRECT` | `True` (prod) | Mematikannya juga mematikan HSTS |
| `CSP_REPORT_ONLY` | `False` (prod) | `True` = CSP hanya dilaporkan, tidak menghalangi |
| `CSP_EXTRA_IMG_SRC` | kosong | Host tambahan untuk gambar (mis. CDN media) |
| `ROUTING_ENGINE` | `naive` | `naive` atau `osrm` |
| `REDIS_URL` | kosong | Kosong → cache memori lokal |
| `USE_SUPABASE_STORAGE` | `False` | `True` bila filesystem host bersifat ephemeral |

---

## Model Domain

```
Instansi ─┬─< User (PETUGAS)
          ├─< Kategori (instansi_default)
          └─< Laporan

Kategori ──< Laporan ─┬─< RiwayatStatus     (jejak audit tiap transisi)
                      ├─< Tanggapan         (percakapan; ada catatan internal)
                      └─< Dukungan          (unik per warga per laporan)

Wilayah (MultiPolygon)   ← spatial join dengan Laporan.lokasi
Fasilitas (Point)        ← analisis kedekatan
```

Catatan desain:

- **Primary key UUID.** Nomor laporan tidak boleh mudah ditebak atau
  dienumerasi lewat URL.
- **Soft delete.** Laporan yang dihapus tetap tersimpan agar riwayat tindak
  lanjut dapat diaudit. Manager `objects` menyaringnya otomatis; `all_objects`
  mengabaikan penyaringan itu.
- **Kolom `lokasi` bertipe `geography`.** Jarak langsung terhitung dalam meter
  di atas permukaan bumi — tidak perlu reproyeksi manual ke SRID metrik.
- **Snapshot nama pelapor.** Relasi ke `User` memakai `SET_NULL`, sementara
  `nama_pelapor` menyimpan salinan nama, sehingga riwayat tetap terbaca
  walaupun akunnya dihapus.

---

### Data Batas Wilayah

Analisis choropleth dan pengisian kelurahan/kecamatan otomatis membutuhkan
tabel `Wilayah` terisi. Repo menyertakan batas **29 kecamatan Kabupaten
Tangerang** (kode BPS `36.03.xx`) di `spatial/data/`.

```bash
# Impor bawaan + membentuk induk tingkat kabupaten dari gabungan kecamatan
python manage.py import_wilayah --induk-nama "Kabupaten Tangerang"

# Periksa dulu tanpa menulis apa pun
python manage.py import_wilayah --dry-run

# Sumber lain dengan nama kolom berbeda
python manage.py import_wilayah \
    --file /path/batas_kelurahan.geojson \
    --tingkat KELURAHAN \
    --nama-field NAMA_KEL --kode-field KODE_KEL
```

Perilaku command:

- **Idempoten** — dijalankan ulang memperbarui geometri, tidak menggandakan baris.
- **Menyaring data cacat** — fitur tanpa nama/kode dilewati dan dilaporkan; kode
  ganda ditolak alih-alih diam-diam menimpa baris sebelumnya.
- **Memperbaiki geometri rusak** lewat `buffer(0)`, yang lazim dibutuhkan pada
  data batas hasil digitasi (satu poligon di berkas bawaan memang perlu ini).
- **Membungkus `Polygon` menjadi `MultiPolygon`** agar berkas dari sumber lain
  tetap dapat dipakai.
- **Menghitung `luas_km2`** lewat `ST_Area(geom::geography)` — menghitung luas
  langsung dari koordinat derajat menghasilkan angka tanpa arti. Nilai ini yang
  dipakai kolom kepadatan per km² pada halaman analitik.
- **`--induk-nama`** membentuk wilayah tingkat KOTA dari gabungan seluruh
  poligon anak, karena berkas bawaan tidak memuat poligon kabupaten.

> Titik laporan di luar cakupan data tidak akan mendapat pengisian wilayah
> otomatis. Sesuaikan `VITE_MAP_CENTER_*` di frontend bila Anda mengimpor
> wilayah lain.

---

## Peran & Otorisasi

| Peran | Cakupan data | Kemampuan |
|---|---|---|
| `WARGA` | Laporan miliknya sendiri | Membuat laporan, mendukung, menanggapi, menarik laporan yang belum diverifikasi |
| `PETUGAS` | Laporan instansinya | Verifikasi, proses, selesaikan, tolak, catatan internal |
| `ADMIN` | Seluruh laporan | Semua kemampuan petugas + disposisi antar instansi, kelola pengguna/instansi/kategori |

Pembatasan diterapkan di **lapisan data**, bukan sekadar menyembunyikan tombol:

```python
# reports/services/laporan_service.py
def queryset_untuk(user):
    if user.is_admin:   return qs
    if user.is_petugas: return qs.filter(instansi_id=user.instansi_id)
    return qs.filter(pelapor_id=user.id)
```

Registrasi publik **selalu** menghasilkan peran `WARGA` — payload yang
menyisipkan `"role": "ADMIN"` diabaikan karena peran ditetapkan di service, dan
hal itu diuji di `tests/integration/test_auth_api.py`.

---

## Alur Status Laporan

```
                  ┌──────────────┐
      ┌──────────►│   DITOLAK    │◄──────────┐
      │           └──────────────┘           │
      │                  ▲                   │
┌─────┴──┐      ┌────────┴─────┐      ┌──────┴───┐      ┌─────────┐
│  BARU  ├─────►│ DIVERIFIKASI ├─────►│ DIPROSES ├─────►│ SELESAI │
└────────┘      └──────────────┘      └──────────┘      └─────────┘
```

Transisi yang sah didefinisikan sekali di `TRANSISI_SAH`
(`reports/services/laporan_service.py`) dan ditegakkan di server. Aturan
tambahan:

- Penolakan **wajib** disertai alasan — pelapor berhak tahu sebabnya.
- Penyelesaian **wajib** disertai catatan tindakan.
- `SELESAI` dan `DITOLAK` bersifat terminal.
- Setiap transisi menulis satu baris `RiwayatStatus` beserta pelakunya.

---

## Daftar Endpoint

Semua respons memakai amplop yang sama:

```jsonc
// sukses
{ "success": true, "message": "Berhasil.", "data": { }, "meta": { } }
// gagal
{ "success": false, "message": "…", "code": "validation_error", "errors": { } }
```

### Autentikasi — `/api/v1/auth/`

| Metode | Path | Akses | Keterangan |
|---|---|---|---|
| POST | `login/` | publik | Mengembalikan profil + pasangan token JWT |
| POST | `logout/` | login | Mencabut refresh token (blacklist) |
| POST | `register/` | publik | Registrasi warga (peran dipaksa `WARGA`) |
| POST | `refresh/` | publik | Menukar refresh token |
| GET/PATCH | `profil/` | login | Baca / perbarui profil sendiri |
| POST | `ubah-sandi/` | login | Ganti kata sandi |
| GET/POST/PATCH/DELETE | `instansi/` | baca: login, tulis: admin | CRUD instansi |
| GET | `pengguna/` | admin | Daftar pengguna |
| POST | `pengguna/internal/` | admin | Buat akun `PETUGAS`/`ADMIN` |
| POST | `pengguna/{id}/aktifkan/` · `nonaktifkan/` | admin | Ubah status akun |

### Laporan — `/api/v1/`

| Metode | Path | Akses | Keterangan |
|---|---|---|---|
| GET | `laporan/` | login | Daftar berpaginasi; lihat filter di bawah |
| POST | `laporan/` | login | Buat laporan (multipart, mendukung foto) |
| GET | `laporan/{id}/` | login | Detail + linimasa + tanggapan |
| DELETE | `laporan/{id}/` | pemilik/admin | Soft delete |
| POST | `laporan/{id}/status/` | petugas/admin | Transisi status |
| POST | `laporan/{id}/alihkan/` | admin | Disposisi ke instansi lain |
| POST | `laporan/{id}/dukungan/` | login | Tambah/batalkan dukungan |
| POST | `laporan/{id}/tanggapan/` | login | Kirim tanggapan |
| GET | `laporan/geojson/` | login | FeatureCollection untuk peta |
| GET | `laporan/statistik/` | login | Ringkasan, per kategori, tren harian |
| GET | `laporan/cek-duplikat/` | login | Deteksi laporan serupa sebelum dikirim |
| GET/POST/PATCH | `kategori/` | baca: publik | CRUD kategori |
| GET | `publik/laporan/` | publik | Peta publik (laporan terverifikasi) |
| GET | `publik/lacak/{tiket}/` | publik | Pelacakan lewat nomor tiket |

**Parameter filter `laporan/`:**
`q`, `status` (boleh berulang), `prioritas`, `kategori`, `instansi`,
`kelurahan`, `kecamatan`, `dari`, `sampai`, `page`, `page_size`,
`bbox=minLon,minLat,maxLon,maxLat`, serta `lat` + `lon` + `radius`.

### Spasial — `/api/v1/spatial/`

| Metode | Path | Akses | Keterangan |
|---|---|---|---|
| GET | `wilayah/` | publik | GeoJSON batas administratif |
| GET | `wilayah/agregasi/` | publik | Jumlah & rasio penyelesaian per wilayah |
| GET | `wilayah/reverse/` | publik | Wilayah dari satu koordinat |
| GET | `heatmap/` | publik | Titik `[lat, lon, bobot]` |
| GET | `laporan-sekitar/` | login | Laporan dalam radius, terurut jarak |
| GET | `fasilitas/` · `fasilitas/terdekat/` | publik / login | Fasilitas publik |
| POST | `rute/` | login | Rute menuju titik laporan |

`GET /api/v1/health/` terbuka untuk probe uptime platform hosting.

---

## Fitur Spasial

- **Query radius** memakai `lokasi__distance_lte` pada kolom `geography`,
  sehingga PostGIS mengembalikan meter sesungguhnya, bukan derajat.
- **Filter viewport** (`bbox`) membatasi data yang dikirim ke peta sesuai area
  yang sedang dilihat pengguna.
- **Deteksi duplikat** mencari laporan sekategori dalam radius 50 m dan 7 hari
  terakhir, lalu frontend menawarkan opsi mendukung laporan yang sudah ada.
- **Agregasi choropleth** melakukan spatial join titik laporan ke poligon
  wilayah, lengkap dengan kepadatan per km² agar wilayah luas dan sempit
  sebanding. Hasilnya di-cache 300 detik.
- **Routing** memakai pola adapter. `ROUTING_ENGINE=osrm` memanggil OSRM dan
  **otomatis jatuh** ke perhitungan haversine bila layanannya tak terjangkau —
  layanan pihak ketiga tidak boleh menjatuhkan request pengguna.

---

## Header Keamanan

`core/middleware/security_headers.py` menjamin enam header berikut ada di
setiap respons:

| Header | Nilai | Sumber |
|---|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` | SecurityMiddleware + fallback |
| `Content-Security-Policy` | `default-src 'self'; script-src 'self'; …; frame-ancestors 'none'` | middleware ini |
| `X-Frame-Options` | `DENY` | XFrameOptionsMiddleware + fallback |
| `X-Content-Type-Options` | `nosniff` | SecurityMiddleware + fallback |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | SecurityMiddleware + fallback |
| `Permissions-Policy` | seluruh sensor dimatikan kecuali `geolocation=(self)` | middleware ini |

Ditambah `Cross-Origin-Opener-Policy: same-origin`,
`Cross-Origin-Resource-Policy: cross-origin`, serta penghapusan header `Server`
dan `X-Powered-By` yang membocorkan detail stack.

Django tidak menyediakan Permissions-Policy secara bawaan, dan CSP-nya perlu
disesuaikan dengan kebutuhan halaman admin — karena itu keduanya disusun
manual. `script-src` sengaja **tanpa** `'unsafe-inline'` maupun
`'unsafe-eval'`.

Memverifikasi:

```bash
python -m pytest tests/unit/test_security_headers.py -v
curl -sI https://api-anda.example.id/api/v1/health/ | grep -iE 'strict|content-security|x-frame|nosniff|referrer|permissions'
```

Di development CSP berjalan **report-only** supaya Vite HMR tidak terhalang.

---

### Pembatasan Laju & Sesi

| Endpoint | Batas | Kunci |
|---|---|---|
| `auth/login/` | 5/menit · 20/menit | Email yang disasar · alamat IP |
| `auth/register/` | 5/jam | Alamat IP |
| `auth/ubah-sandi/` | 5/menit | Pengguna |

Login dibatasi dua lapis. Pembatasan per-IP saja mudah dilewati lewat kumpulan
proxy, sekaligus berisiko mengunci banyak pengguna sah yang berbagi satu IP
publik (kantor, NAT seluler); pembatasan per-email menutup celah pertama, dan
batas IP yang longgar menutup yang kedua.

Pelampauan batas dijawab **429** dengan amplop error yang sama seperti endpoint
lain — bukan 403 seperti bawaan `django-ratelimit`, karena masalahnya frekuensi,
bukan izin.

> **Penting:** penghitung rate limit disimpan di cache. `LocMemCache` bersifat
> per-proses, sehingga dengan beberapa worker gunicorn batas efektifnya berlipat
> dan tidak dapat diandalkan. **Isi `REDIS_URL` bila layanan diekspos ke
> publik.**

Sesi memakai `ROTATE_REFRESH_TOKENS` + `BLACKLIST_AFTER_ROTATION`, sehingga
refresh token yang sudah ditukar langsung dicabut. Endpoint `auth/logout/`
mencabut token secara eksplisit — tanpa itu, menghapus token di sisi klien
tidak membuatnya tidak berlaku, dan token yang tercuri tetap sah sampai masa
berlakunya habis (7 hari).

---

## Pengujian

```bash
pytest                  # seluruh berkas uji
pytest -m unit          # cepat, tanpa database penuh
pytest -m integration   # butuh PostGIS aktif
pytest --cov=. --cov-report=term-missing
```

Cakupan saat ini: **65 pengujian**.

| Berkas | Yang dijaga |
|---|---|
| `unit/test_state_machine.py` | Tidak ada status yang bisa dilompati |
| `unit/test_security_headers.py` | Header tidak melonggar; HSTS hanya di HTTPS |
| `unit/test_routing_adapter.py` | Jarak haversine wajar; fallback adapter jalan |
| `unit/test_nomor_tiket.py` | Format tiket & ketidak-berurutannya |
| `integration/test_laporan_api.py` | Alur warga→petugas, isolasi data antar peran |
| `integration/test_auth_api.py` | Registrasi tidak bisa menaikkan peran sendiri |
| `integration/test_auth_hardening.py` | Batas laju benar-benar menyala; token dicabut saat logout & rotasi |
| `integration/test_import_wilayah.py` | Impor idempoten & menyaring data cacat; reverse-lookup mengembalikan tingkat paling spesifik |
| `integration/test_kesiapan.py` | Pemeriksa kesiapan menangkap konfigurasi berbahaya & akun demo |

---

## Integrasi Berkelanjutan

`.github/workflows/ci.yml` berjalan pada setiap push ke `main`/`develop` dan
setiap pull request:

| Job | Isi |
|---|---|
| **Lint & Format** | `ruff check` dan `black --check`. Versi keduanya dibaca langsung dari `requirements/development.txt`, supaya CI dan mesin lokal memakai formatter yang sama persis |
| **Pytest** | Menjalankan seluruh pengujian di atas layanan PostGIS 17-3.5, lengkap dengan `manage.py check` dan pemeriksaan migrasi tertinggal. Laporan coverage diunggah sebagai artifact |
| **Build image** | Membangun `Dockerfile` (tanpa push) agar kesalahan pada image produksi ketahuan sebelum deploy |

Pemeriksaan migrasi (`makemigrations --check --dry-run`) sengaja disertakan:
perubahan model yang lupa dibuatkan migrasinya akan lolos pengujian biasa,
tetapi menggagalkan `migrate` saat container produksi dinyalakan.

---

## Kesiapan Produksi

Dua command membantu memastikan instalasi tidak dilepas ke publik dalam
keadaan setengah jadi.

```bash
python manage.py cek_kesiapan          # laporan lengkap
python manage.py cek_kesiapan --ketat  # peringatan pun dianggap gagal (CI)
```

Yang diperiksa: `DEBUG`, `SECRET_KEY` bawaan, `ALLOWED_HOSTS` kosong/wildcard,
pengalihan HTTPS & HSTS, CSP masih report-only, origin `localhost` yang
tertinggal di CORS, cache non-Redis (membuat rate limit tidak andal),
penyimpanan media ephemeral, akun demo yang masih hidup, data wilayah kosong,
dan kategori yang belum dipetakan ke instansi.

Kode keluarnya 1 bila ada masalah, sehingga dapat dipasang sebagai gerbang
rilis. Ini melengkapi `manage.py check --deploy` bawaan Django, yang hanya
memeriksa setelan keamanan umum dan tidak tahu apa pun tentang isi database.

```bash
python manage.py amankan_akun_demo              # nonaktifkan (default)
python manage.py amankan_akun_demo --acak-sandi # tetap aktif, sandi diacak
python manage.py amankan_akun_demo --dry-run    # lihat dampaknya dulu
```

Akun dari `seed_demo` memakai kata sandi yang tertulis terbuka di README ini.
Berguna saat pengembangan, berbahaya begitu layanan dapat diakses siapa saja.

> `--hapus` menghapus akun **permanen** — model `User` tidak memakai soft
> delete. Laporan yang pernah dibuat tetap tersimpan karena relasi pelapor
> bersifat `SET_NULL` dan namanya sudah disalin ke `nama_pelapor`.

Setelah live, uji dari luar:

```bash
./scripts/verifikasi_deploy.sh https://domain-api-anda
```

Skrip itu memeriksa layanan hidup, database terjangkau, keenam header
keamanan, pengalihan HTTP→HTTPS, endpoint publik terbuka, endpoint privat
menolak tanpa token, dan data wilayah benar-benar terisi.

---

## Deployment

### Opsi A — Container (Hugging Face Spaces, Fly.io, Railway)

`Dockerfile` sudah menyiapkan runtime GeoDjango, berjalan sebagai UID 1000, dan
mendengarkan port `7860` (bawaan HF Spaces).

```bash
docker build -t titiklapor-api .
docker run -p 7860:7860 --env-file .env titiklapor-api
```

Variabel wajib di panel platform: `SECRET_KEY`, `DJANGO_ENV=production`,
`HOSTS`, `DB_*`, `DB_SSLMODE=require`, `CORS_ORIGINS`, `CSRF_TRUSTED_ORIGINS`.
Bila filesystem host bersifat ephemeral (HF Spaces), aktifkan
`USE_SUPABASE_STORAGE=True` agar foto laporan tidak hilang saat container
di-restart.

Migrasi dan `collectstatic` dijalankan otomatis saat container start.

### Opsi B — VPS + Gunicorn + Nginx

```bash
pip install -r requirements/production.txt
export DJANGO_ENV=production
python manage.py migrate && python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3 --timeout 120
```

Konfigurasi Nginx (termasuk proxy `/api/` dan header keamanan) tersedia di
repositori frontend: `deploy/nginx/titiklapor.conf`.

> Di belakang reverse proxy, pastikan Nginx mengirim
> `proxy_set_header X-Forwarded-Proto $scheme;` — tanpa itu Django mengira
> koneksinya HTTP dan HSTS tidak akan dikirim.

Runbook lengkap end-to-end (Supabase → backend → frontend) ada di
`docs/DEPLOYMENT.md` pada repositori frontend.

---

## Alur Kerja Git

Repositori ini mengikuti **Git Flow** yang disederhanakan:

```
main      ← rilis produksi (selalu dapat di-deploy)
 └ develop    ← integrasi
    ├ feature/be-<modul>
    ├ fix/<ringkas>
    └ hotfix/<ringkas>   ← langsung dari main untuk perbaikan darurat
```

```bash
# 1. Cabang fitur dari develop
git switch develop && git pull
git switch -c feature/be-notifikasi
# … kerjakan, commit bertahap …

# 2. Gabungkan ke develop (masih boleh lokal — develop tidak diproteksi)
git switch develop && git merge --no-ff feature/be-notifikasi
git push origin develop

# 3. Rilis ke main WAJIB lewat pull request
gh pr create --base main --head develop --fill
gh pr checks --watch          # tunggu CI hijau
gh pr merge --merge           # baru bisa di-merge setelah semua cek lulus

# 4. Samakan develop dengan main
git switch develop && git merge --ff-only main && git push origin develop
```

### Proteksi Branch `main`

`main` diproteksi, jadi `git push origin main` akan **ditolak**. Aturannya:

| Aturan | Nilai |
|---|---|
| Cek CI wajib lulus | `Lint & Format`, `Pytest (Python 3.12)`, `Build image` |
| Branch harus mutakhir sebelum merge | Ya |
| Force-push & hapus branch | Dilarang untuk semua |
| Berlaku untuk admin | **Tidak** — pemilik repo tetap bisa menembus bila mendesak |

Review wajib **tidak** diaktifkan dengan sengaja: GitHub melarang menyetujui
pull request sendiri, sehingga pada repositori satu orang aturan itu akan
mengunci merge selamanya.

Jalan darurat (pakai seperlunya, dan sebutkan alasannya di pesan commit):

```bash
gh api -X DELETE repos/<user>/<repo>/branches/main/protection   # matikan
# … perbaiki …
gh api -X PUT  repos/<user>/<repo>/branches/main/protection --input proteksi.json
```

### Konvensi Pesan Commit

`<tipe>(<cakupan>): <ringkasan dalam bahasa Indonesia, huruf kecil>`

| Tipe | Untuk |
|---|---|
| `feat` | Kemampuan baru |
| `fix` | Perbaikan bug |
| `refactor` | Perubahan struktur tanpa mengubah perilaku |
| `test` | Penambahan/perubahan pengujian |
| `docs` | Dokumentasi |
| `chore` | Migrasi, konfigurasi, pekerjaan rutin |
| `build` | Dependensi & berkas build/deploy |

Satu commit = satu gagasan utuh. Contoh dari riwayat repositori ini:

```
feat(reports): tambah layanan bisnis laporan
feat(core): tambah middleware header keamanan HTTP
test: tambah pengujian unit & integrasi
chore: tambah migrasi awal users, reports & spatial
```

Badan commit menjelaskan **alasan**, bukan mengulang daftar berkas yang sudah
terlihat pada diff.

---

## Lisensi

MIT.
