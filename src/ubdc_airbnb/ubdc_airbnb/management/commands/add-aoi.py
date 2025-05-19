from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from mercantile import LngLatBbox

from ubdc_airbnb.models import AOIShape
from ubdc_airbnb.utils import get_random_string
from ubdc_airbnb.utils.spatial import get_geom_from_bbox


class Command(BaseCommand):
    help = """
    Import an Area-Of-Interest Boundary into the system.

    The boundary must be a Polygon or MultiPolygon.
    Coordinates must be in WGS84 (EPSG:4326).
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
        file_type = None
        geom = None
        name = options["name"] or f"AOI-{get_random_string(8)}"
        description = options["description"] or "Imported AOI"
        notes = {
            "description": description,
        }

        if options["bbox"]:
            bbox = options["bbox"]
            coords = bbox.split(",")
            if len(coords) != 4:
                msg = "Bounding box must have 4 coordinates (minx,miny,maxx,maxy)"
                raise CommandError(msg)
            geom = get_geom_from_bbox(LngLatBbox(*map(float, coords)))

        if geom is None:
            msg = "Invalid geometry provided"
            raise CommandError(msg)

        geom_3857 = geom.transform(3857, clone=True)

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
