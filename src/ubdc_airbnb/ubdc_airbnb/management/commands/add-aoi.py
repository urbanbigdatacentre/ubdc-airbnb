import glob
import os
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from ubdc_airbnb.models import AOIShape

from . import _GeoFileHandler

# from ubdc_airbnb.utils.grids import generate_initial_grid


def add_file(geo_file) -> AOIShape:
    geo_object = _GeoFileHandler(geo_file)

    try:
        username = os.getlogin()
    except:
        username = "unknown"

    aoi_obj = AOIShape.objects.create(
        geom_3857=geo_object.convert(),
        name=geo_object.name,
        notes={
            "user": username,
            "path": Path(geo_file).parent.as_posix(),
            "name": Path(geo_file).name,
            "import_date": datetime.utcnow(),
        },
    )
    return aoi_obj


class Command(BaseCommand):
    help = """Import an Area-Of-Interest Boundary into the system.
    - The boundary must be a Polygon or MultiPolygon.
    - The file must be a Shapefile or GeoJSON.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--create-grid",
            help="create initial grid after writing the geo-files. Default is False",
            dest="create_grid",
            action="store_true",
        )
        parser.set_defaults(create_grid=False)
        parser.add_argument(
            "--geo-file",
            type=str,
            help="Path to file to be stored; Files are parsed by glob. Example: **/*.shp",
        )

    def handle(self, *args, **options):
        # not implemented yet
        pass
