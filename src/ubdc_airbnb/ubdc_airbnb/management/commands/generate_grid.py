from argparse import ArgumentParser, ArgumentTypeError

from django.core.management import BaseCommand

from ubdc_airbnb.tasks import task_tidy_grids
from ubdc_airbnb.utils.grids import generate_initial_grid

input_choices = ["aoi", "quadkey"]


def check_positive(value) -> int:
    value = int(value)
    if value < 0:
        raise ArgumentTypeError(f"{value} must be positive integer.")

    return value


class Command(BaseCommand):
    help = "Generates grid tiles based on either an AOI ID (by default) or a Quadkey."

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument(
            "input-value",
            type=str,
            help="The input value to generate grids. Either an AOI ID or a Quadkey",
        )
        parser.add_argument(
            "--input-type",
            dest="input-type",  # to keep it consistent with input-type
            choices=input_choices,
            default="aoi",
        )
        # parser.add_argument("--no-tidy", action="store_false")

    def handle(self, *args, **options):

        tidy = False
        input_value = options["input-value"]
        input_type = options["input-type"]

        if input_type == "quadkey":
            assert input_value.startswith("0")
            from ubdc_airbnb.models import UBDCGrid

            UBDCGrid.objects.create_from_quadkey(
                quadkey=input_value,
                save=True,
                allow_overlap_with_currents=False,
            )
            pass
        if input_type == "aoi":
            ## generate aoi
            grids = generate_initial_grid(aoishape_id=input_value)

        if tidy:
            task_tidy_grids(less_than=50)
