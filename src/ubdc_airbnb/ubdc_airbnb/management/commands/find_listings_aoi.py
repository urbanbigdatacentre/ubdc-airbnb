import concurrent.futures
from argparse import ArgumentParser, ArgumentTypeError

from django.core.management import BaseCommand
from django.db.models import QuerySet

from ubdc_airbnb.models import UBDCGrid
from ubdc_airbnb.tasks import task_discover_listings_at_grid
from . import int_to_aoi


def check_positive(value) -> int:
    value = int(value)
    if value < 0:
        raise ArgumentTypeError(f"{value} must be positive integer.")

    return value


class Command(BaseCommand):
    help = "AOI designated by its AOI-ID for listings."

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument('aoi', type=int_to_aoi)
        parser.add_argument('--workers', type=check_positive, default=2, help="Number of workers/threads for this "
                                                                              "operation. Default 2")

    def handle(self, *args, **options):
        aoi = options['aoi']
        workers = options['workers']

        self.stdout.write(self.style.NOTICE(f'Scanning for listings at AOI: {aoi}'))
        grids: QuerySet = UBDCGrid.objects.filter(geom_3857__intersects=aoi.geom_3857)

        if grids.exists():
            quadkeys = list(grids.values_list('quadkey', flat=True))
            func = task_discover_listings_at_grid
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                futures = []
                for qk in quadkeys:
                    future = executor.submit(func, quadkey=qk)
                    futures.append(future)
                for future in concurrent.futures.as_completed(futures):
                    try:
                        data = future.result()
                    except Exception as exc:
                        self.stdout.write(self.style.ERROR(f'error:%s') % exc)
