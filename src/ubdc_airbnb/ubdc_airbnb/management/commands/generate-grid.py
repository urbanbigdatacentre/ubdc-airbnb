from argparse import ArgumentParser, ArgumentTypeError

from django.core.management import BaseCommand

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

    def handle(self, *args, **options):

        tidy = False
        input_value = options["input-value"]
        input_type = options["input-type"]

        if input_type == "quadkey":
            assert len(input_value) > 5, "Quadkey must be at least 2 characters long."
            from ubdc_airbnb.models import UBDCGrid

            UBDCGrid.objects.create_from_quadkey(quadkey=input_value)

        if input_type == "aoi":
            from ubdc_airbnb.models import AOIShape

            try:
                aoi = AOIShape.objects.get(id=input_value)
            except AOIShape.DoesNotExist:
                raise ValueError(f"AOI with ID {input_value} does not exist.")

            aoi.create_grid()
