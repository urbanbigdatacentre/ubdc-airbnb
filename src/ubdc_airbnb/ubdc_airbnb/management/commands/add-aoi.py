from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from mercantile import LngLatBbox

from ubdc_airbnb.models import AOIShape
from ubdc_airbnb.utils import get_random_string
from ubdc_airbnb.utils.spatial import get_geom_from_bbox


class Command(BaseCommand):
    help = """
    Import an Area-Of-Interest Boundary into the system.
    - The boundary must be a Polygon or MultiPolygon.
    - Coordinates must be in WGS84 (EPSG:4326).
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--name",
            type=str,
            help="Name of the AOI",
        )
        parser.add_argument(
            "--description",
            type=str,
            help="Description of the AOI",
        )
        group = parser.add_mutually_exclusive_group(required=True)
        # Add more methos of importing AOIs; all mutally exclusive
        group.add_argument(
            "--bbox",
            type=str,
            help="Bounding that can be used to create an AOI. e.g '1.0,2.0,3.0,4.0' (minx,miny,maxx,maxy)",
        )

    def handle(self, *args, **options):
        geo_file = None
        file_type = None
        name = options["name"] or f"AOI-{get_random_string(8)}"
        description = options["description"] or "Imported AOI"
        notes = {
            "description": description,
        }

        if options["bbox"]:
            geo_file = options["bbox"]
            coords = geo_file.split(",")
            if len(coords) != 4:
                self.stderr.write(self.style.ERROR("Invalid bounding box provided."))
                return
            geom = get_geom_from_bbox(LngLatBbox(*map(float, coords)))

        if geom is None:
            self.stderr.write(self.style.ERROR("Invalid geometry provided."))
            return
        geom_3857 = geom.transform(3857, clone=True)
        # Check that the geometry is valid
        if not geom_3857.valid:
            self.stderr.write(self.style.ERROR(f"Invalid geometry ({geom.valid_reason}): {geom.wkt}"))
            return
        if geom_3857.area < 0:
            self.stderr.write(self.style.ERROR(f"Invalid geometry (area less or equal to zero (0)): {geom.wkt}"))
            return

        # Add the new AOI
        try:
            with transaction.atomic():
                aoi = AOIShape.objects.create(
                    name=name,
                    notes=notes,
                    geom_3857=geom_3857,
                )
                self.stdout.write(self.style.SUCCESS(f'Successfully added {file_type} AOI "{aoi.name}" (ID: {aoi.pk})'))
                new_grids_number = aoi.create_grid()
                self.stdout.write(self.style.SUCCESS(f'Created {new_grids_number} grids for AOI "{aoi.name}"'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to add AOI: {str(e)}"))
