#!/usr/bin/env bash
# ============================================================================
# Uji asap (smoke test) API Titik Lapor yang sudah live.
#
#   ./scripts/verifikasi_deploy.sh https://user-space.hf.space
#
# Memeriksa hal-hal yang hanya bisa dibuktikan setelah deploy: layanan hidup,
# database terjangkau, header keamanan terpasang, endpoint publik terbuka,
# endpoint privat tertutup, dan HTTP dialihkan ke HTTPS.
#
# Keluar 1 bila ada pemeriksaan yang gagal — aman dipakai di pipeline.
# ============================================================================
set -uo pipefail

BASE="${1:-}"
if [[ -z "$BASE" ]]; then
  echo "Pakai: $0 <url-api>   (mis. https://user-space.hf.space)" >&2
  exit 2
fi
BASE="${BASE%/}"
API="$BASE/api/v1"

LULUS=0
GAGAL=0

lulus() { printf '  \033[32m✓\033[0m %s\n' "$1"; LULUS=$((LULUS+1)); }
gagal() { printf '  \033[31m✗\033[0m %s\n' "$1"; GAGAL=$((GAGAL+1)); }

# Bandingkan kode status HTTP yang diterima dengan yang diharapkan.
cek_status() {
  local nama="$1" url="$2" harap="$3"
  local kode
  kode=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$url" 2>/dev/null)
  if [[ "$kode" == "$harap" ]]; then
    lulus "$nama ($kode)"
  else
    gagal "$nama — diharapkan $harap, diterima $kode"
  fi
}

echo "Verifikasi $BASE"
echo "══════════════════════════════════════════════════════════════"

# ── 1. Layanan & database ───────────────────────────────────────────────────
echo "Layanan"
HEALTH=$(curl -sS --max-time 20 "$API/health/" 2>/dev/null)
if echo "$HEALTH" | grep -q '"service"'; then
  lulus "health check menjawab"
  if echo "$HEALTH" | grep -q '"database": *true'; then
    lulus "database terjangkau"
  else
    gagal "database TIDAK terjangkau — periksa kredensial DB_*"
  fi
else
  gagal "health check tidak menjawab (layanan mati atau URL salah)"
fi

# ── 2. Header keamanan ──────────────────────────────────────────────────────
echo
echo "Header keamanan"
HEADER=$(curl -sS -D - -o /dev/null --max-time 20 "$API/health/" 2>/dev/null \
         | tr '[:upper:]' '[:lower:]')

for h in strict-transport-security content-security-policy x-frame-options \
         x-content-type-options referrer-policy permissions-policy; do
  if echo "$HEADER" | grep -q "^$h:"; then
    lulus "$h"
  elif [[ "$h" == "content-security-policy" ]] \
       && echo "$HEADER" | grep -q "^content-security-policy-report-only:"; then
    # Report-only mencatat pelanggaran tanpa memblokirnya — bukan perlindungan.
    gagal "content-security-policy masih report-only (set CSP_REPORT_ONLY=False)"
  else
    gagal "$h tidak terpasang"
  fi
done

if echo "$HEADER" | grep -q "^server:"; then
  printf '  \033[33m!\033[0m header Server sebaiknya disembunyikan\n'
fi

# ── 3. Pengalihan HTTPS ─────────────────────────────────────────────────────
echo
echo "HTTPS"
if [[ "$BASE" == https://* ]]; then
  KODE_HTTP=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 \
              "${BASE/https:/http:}/api/v1/health/" 2>/dev/null)
  if [[ "$KODE_HTTP" =~ ^30[1278]$ ]]; then
    lulus "http dialihkan ke https ($KODE_HTTP)"
  else
    gagal "http TIDAK dialihkan — diterima $KODE_HTTP"
  fi
else
  gagal "URL bukan https — HSTS & cookie aman tidak akan bekerja"
fi

# ── 4. Endpoint publik terbuka ──────────────────────────────────────────────
echo
echo "Endpoint publik"
cek_status "daftar kategori"       "$API/kategori/"        200
cek_status "peta laporan publik"   "$API/publik/laporan/"  200
cek_status "batas wilayah"         "$API/spatial/wilayah/" 200

JML_WILAYAH=$(curl -sS --max-time 20 "$API/spatial/wilayah/" 2>/dev/null \
              | grep -o '"type": *"Feature"' | wc -l | tr -d ' ')
if [[ "${JML_WILAYAH:-0}" -gt 0 ]]; then
  lulus "data wilayah terisi ($JML_WILAYAH fitur)"
else
  gagal "data wilayah KOSONG — jalankan import_wilayah"
fi

# ── 5. Endpoint privat tertutup ─────────────────────────────────────────────
echo
echo "Otorisasi"
cek_status "daftar laporan menolak tanpa token"  "$API/laporan/"        401
cek_status "manajemen pengguna menolak"          "$API/auth/pengguna/"  401
cek_status "profil menolak tanpa token"          "$API/auth/profil/"    401

# ── 6. Halaman admin ────────────────────────────────────────────────────────
echo
echo "Panel admin"
KODE_ADMIN=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$BASE/admin/login/" 2>/dev/null)
if [[ "$KODE_ADMIN" == "200" ]]; then
  lulus "panel admin dapat diakses ($KODE_ADMIN)"
else
  printf '  \033[33m!\033[0m panel admin menjawab %s\n' "$KODE_ADMIN"
fi

# ── Ringkasan ───────────────────────────────────────────────────────────────
echo
echo "══════════════════════════════════════════════════════════════"
echo "  $LULUS lulus, $GAGAL gagal"

if [[ $GAGAL -gt 0 ]]; then
  echo "  Deploy BELUM siap dipakai." >&2
  exit 1
fi
echo "  Semua pemeriksaan lulus."
