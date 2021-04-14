#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import sysconfig
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

conda_venv_base = Path(sysconfig.get_paths()["data"])
os.environ.setdefault("PROJ_LIB", os.getenv('PROJ_LIB', conda_venv_base.joinpath(
    "Library/share/proj").as_posix() if conda_venv_base.joinpath(
    "Library/share/proj").is_dir() else None))


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dj_airbnb.settings')

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
