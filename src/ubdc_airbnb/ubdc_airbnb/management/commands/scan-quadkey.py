from django.core.management import BaseCommand
from argparse import ArgumentParser
from ubdc_airbnb.models import UBDCGrid


class Command(BaseCommand):
    help = "Scan a quadkey-grid for listings. The quadkey must exist in the database."

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument("quadkey", type=str)

    def handle(self, *args, **options):
        quadkey = options["quadkey"]
        # Check if the grid exists; throw an error if it doesn't
        try:
            grid = UBDCGrid.objects.get(quadkey=quadkey)
        except UBDCGrid.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Grid with quadkey {quadkey} does not exist."))
            self.stderr.write("You can add it with the add_quadkey command.")
            self.stderr.write("Exiting")
            return
        self.stdout.write(self.style.SUCCESS(f"Submitting Task to scan Grid: {quadkey} for new listings"))
        from ubdc_airbnb.tasks import task_register_listings_or_divide_at_quadkey

        task = task_register_listings_or_divide_at_quadkey.s(quadkey=quadkey).apply_async()
        self.stdout.write(self.style.SUCCESS(f"Task {task.id} sent to the queue"))
