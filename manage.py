#!/usr/bin/env python
"""Entry point CLI Django untuk Titik Lapor."""
import os
import sys


def main() -> None:
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        f"config.settings.{os.environ.get('DJANGO_ENV', 'development')}",
    )
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Django tidak ditemukan. Aktifkan virtualenv & jalankan "
            "`pip install -r requirements/development.txt`."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
