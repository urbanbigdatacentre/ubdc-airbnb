from argparse import ArgumentParser, ArgumentTypeError

from celery import group
from django.core.management import BaseCommand
from django.db.models import QuerySet

from app.models import UBDCGrid, AOIShape, UBDCGroupTask
from app.tasks import task_estimate_listings_or_divide


def check_positive(value) -> int:
    value = int(value)
    if value < 0:
        raise ArgumentTypeError(f"{value} must be positive integer.")

    return value


class Command(BaseCommand):
    help = """Queries the approximate number of listings in the grids intersecting the provided AOI. Needs an active 
    worker. """

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument('aoi', type=check_positive)

    def handle(self, *args, **options):
        aoishape_id = options['aoi']

        self.stdout.write(self.style.NOTICE(f'Sensing grids on aoi {aoishape_id}'))
        self.stdout.write(self.style.WARNING(f'This command requires at least one worker up and running.'))

        aoi = AOIShape.objects.get(id=aoishape_id)
        grids: QuerySet = UBDCGrid.objects.filter(geom_3857__intersects=aoi.geom_3857)
        if grids.exists():
            less_than: int = 50
            quadkeys = list(grids.values_list('quadkey', flat=True))
            groupTask = group(task_estimate_listings_or_divide.s(quadkey=qk, less_than=less_than) for qk in quadkeys)
            group_result = groupTask.apply_async()
            group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
            group_task.op_name = task_estimate_listings_or_divide.name
            group_task.op_kwargs = {'quadkey': quadkeys, 'less_than': less_than}
            group_task.save()

            return group_result.id
