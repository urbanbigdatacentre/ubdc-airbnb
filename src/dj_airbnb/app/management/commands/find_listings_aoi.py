from argparse import ArgumentParser, ArgumentTypeError
import concurrent.futures

from django.core.management import BaseCommand
from django.db.models import QuerySet

from app.models import UBDCGrid, AOIShape
from app.tasks import task_discover_listings_at_grid


def check_positive(value) -> int:
    value = int(value)
    if value < 0:
        raise ArgumentTypeError(f"{value} must be positive integer.")

    return value


class Command(BaseCommand):
    help = "AOI designated by its AOI-ID for listings."

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument('aoi', type=check_positive)

    def handle(self, *args, **options):
        aoishape_id = options['aoi']

        aoi = AOIShape.objects.get(id=aoishape_id)

        self.stdout.write(self.style.NOTICE(f'Scanning for listings at AOI: {aoi}'))
        grids: QuerySet = UBDCGrid.objects.filter(geom_3857__intersects=aoi.geom_3857)

        if grids.exists():
            quadkeys = list(grids.values_list('quadkey', flat=True))
            func = task_discover_listings_at_grid
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = []
                for qk in quadkeys:
                    future = executor.submit(func, quadkey=qk)
                    futures.append(future)
