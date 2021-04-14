from argparse import ArgumentParser, ArgumentTypeError

from django.core.management import BaseCommand, call_command

from app.utils.grids import generate_initial_grid, tidy_grids


def check_positive(value) -> int:
    value = int(value)
    if value < 0:
        raise ArgumentTypeError(f"{value} must be positive integer.")

    return value


class Command(BaseCommand):
    help = "Generates initial grid based on the AOI and then tidies the database"

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument('aoi', type=check_positive)
        parser.add_argument('--no-tidy', action="store_false")

    def handle(self, *args, **options):
        tidy = options['no_tidy']
        aoishape_id = options['aoi']

        self.stdout.write(self.style.NOTICE(f'Generating Initial Grids'))
        final_grids = generate_initial_grid(aoishape_id=aoishape_id)
        self.stdout.write(self.style.NOTICE(f'Successfully generated grids {len(final_grids)}'))

        if tidy:
            tidy_grids(less_than=50)
