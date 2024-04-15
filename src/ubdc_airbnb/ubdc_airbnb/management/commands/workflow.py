from argparse import ArgumentParser, ArgumentTypeError

from core.celery import app as celery_app
from django.core.management.base import BaseCommand

from ubdc_airbnb.operations import (
    op_discover_new_listings_periodical,
    op_estimate_listings_or_divide_periodical,
    op_get_booking_detail_periodical,
    op_update_calendar_periodical,
    op_update_listing_details_periodical,
    op_update_reviews_periodical,
)
from ubdc_airbnb.tasks import (  # task_register_listings_or_divide_at_aoi,
    task_discover_listings_at_grid,
    task_register_listings_or_divide_at_quadkey,
    task_update_calendar,
)

workflow_options = [
    "get-calendar",
    "get-listing-details",
    "discover-listings",
]


def check_positive(value) -> int:
    value = int(value)
    if value < 0:
        raise ArgumentTypeError(f"{value} must be positive integer.")

    return value


class Command(BaseCommand):
    help = "Import AOI to the database from a shapefile/geojson."

    def add_arguments(self, parser: ArgumentParser):
        wkflow = parser.add_subparsers(dest="workflow", required=True)
        for option in workflow_options:
            p = wkflow.add_parser(option)
            p.add_argument("--as-task", type=check_positive, help="Run this workflow as task.")
            p.add_argument("input-value")
            match option:
                case "discover-listings":
                    p.add_argument(
                        "--input-type",
                        dest="input-type",
                        choices=["quadkey", "aoi"],
                        default="quadkey",
                    )
                case "get-calendar":
                    # additional values for the calendar
                    pass
                case "get-listing-details":
                    # additional values for the listing details
                    pass
                case _:
                    pass

    def handle(self, *args, **options):
        match options.get("workflow"):
            case "discover-listings":
                if options["input-type"] == "quadkey":
                    kwargs = {"quadkey": options["input-value"]}
                    name = task_register_listings_or_divide_at_quadkey.name
                # if options["input-type"] == "aoi":
                #     kwargs = {"aoi_pk": options["input-value"]}
                #     name = task_register_listings_or_divide_at_aoi.name
            case "get-calendar":
                name = task_update_calendar.name
                kwargs = {"listing_id": options["input-value"]}

            case _:
                self.stdout.write("No valid workflow specified.")
                return

        result = celery_app.send_task(name=name, kwargs=kwargs)
        self.stdout.write(f"Job submitted with id {result.id}")
