from argparse import ArgumentParser

from django.core.management import BaseCommand

# Submit a Celery task to find new listings in a grid
# TODO: [COMMAND][FIND-LISTINGS] Allow to specify Area-Of-Interest (AOI) as well.


class Command(BaseCommand):
    help = "Find new new listings in a Grid"

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument("quadkey", type=str)
        parser.add_argument("--as-task", action="store_true")

    def handle(self, *args, **options):
        quadkey = options["quadkey"]
        self.stdout.write(self.style.SUCCESS(f"Scanning grid {quadkey} for new listings"))
        from ubdc_airbnb.tasks import task_discover_listings_at_grid

        task = task_discover_listings_at_grid.s(quadkey=quadkey).apply_async()
        print(f"Task {task.id} sent to the queue")
