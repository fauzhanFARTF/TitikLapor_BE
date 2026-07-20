"""Format & keunikan nomor tiket."""

import re
from datetime import date

import pytest

from reports.services.laporan_service import _generate_nomor_tiket

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

POLA = re.compile(r"^TL-\d{8}-[0-9A-F]{4}$")


def test_format_nomor_tiket_sesuai_pola():
    nomor = _generate_nomor_tiket()
    assert POLA.match(nomor), nomor
    assert date.today().strftime("%Y%m%d") in nomor


def test_nomor_tiket_tidak_berurutan():
    """Nomor acak mencegah penebakan tiket milik warga lain."""

    nomor = {_generate_nomor_tiket() for _ in range(25)}
    assert len(nomor) == 25
