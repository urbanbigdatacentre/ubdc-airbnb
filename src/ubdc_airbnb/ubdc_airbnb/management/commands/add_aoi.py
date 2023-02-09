import glob
import os
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from ubdc_airbnb.models import AOIShape
from ubdc_airbnb.utils.grids import generate_initial_grid
from . import _GeoFileHandler


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
    help = "Import AOI to the database from a shapefile/geojson."

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
        geo_file = options["geo_file"]
        create_initial_grid = options["create_grid"]
        files = glob.glob(geo_file)
        aoi_ids = []
        try:
            with transaction.atomic():
                for f in files:
                    aoi_obj = add_file(f)
                    aoi_ids.append(aoi_obj.id)
                    self.stdout.write(self.style.SUCCESS(f"Successfully imported boundary with id: {aoi_obj.id}"))

                if create_initial_grid:
                    self.stdout.write(self.style.NOTICE(f"Generating Initial Grids"))
                    for obj_id in aoi_ids:
                        final_grids = generate_initial_grid(aoishape_id=obj_id)
                    self.stdout.write(self.style.NOTICE(f"Successfully generated grids {len(final_grids)}"))

        except Exception as excp:
            self.stdout.write(self.style.ERROR(f"An error has occurred. Db was reverted back to its original state"))
            raise excp
