from argparse import ArgumentParser, ArgumentTypeError

from django.core.management import BaseCommand


class Command(BaseCommand):
    help = "Scans the grid for new listings."

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument("quadkey", type=str)
        parser.add_argument("--as-task", action="store_true")

    def handle(self, *args, **options):
        quadkey = options["qk"]
        print(f"Scanning grid {quadkey} for new listings")
        from ubdc_airbnb.tasks import task_discover_listings_at_grid

        task = task_discover_listings_at_grid.s(quadkey=quadkey).apply_async()
        print(f"Task {task.id} sent to the queue")
