import random
import string

from django.core.management.base import BaseCommand


def generate_random_string(length=5):
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for i in range(length))


class Command(BaseCommand):
    help = "Do you need a test area? This command will create one for you based on the quadkey you provide."

    def add_arguments(self, parser):
        parser.add_argument("quadkey", type=str, help="Quadkey parameter (must start with 0)")

    def handle(self, *args, **kwargs):
        quadkey = kwargs["quadkey"]
        from django.contrib.gis.geos import MultiPolygon

        from ubdc_airbnb.models import AOIShape, UBDCGrid

        grid = UBDCGrid.objects.create_from_quadkey(quadkey=quadkey)

        # Buffer the geometry by 100 meters to emulate a real area
        buffered_geometry = grid.geom_3857.buffer(100)

        # Cast the resulting geometry as multipolygon; needed for the AOIShape model
        multipolygon_geometry = MultiPolygon(buffered_geometry)

        # Create AOIShape record, w all collection flags set to True
        AOIShape.objects.create(
            name=f"Test-Area-{generate_random_string()}",
            collect_calendars=True,
            collect_listing_details=True,
            collect_reviews=True,
            collect_bookings=True,
            geom_3857=multipolygon_geometry,
        )

        self.stdout.write(self.style.SUCCESS("Command executed successfully"))
