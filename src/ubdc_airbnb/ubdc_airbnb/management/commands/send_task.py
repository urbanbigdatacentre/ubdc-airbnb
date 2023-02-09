from argparse import ArgumentParser, ArgumentTypeError

from django.core.management.base import BaseCommand

from core.celery import app as celery_app
from ubdc_airbnb.operations import (
    op_discover_new_listings_periodical,
    op_estimate_listings_or_divide_periodical,
    op_update_listing_details_periodical,
    op_update_calendar_periodical,
    op_update_reviews_periodical,
    op_get_booking_detail_periodical,
)
from ubdc_airbnb.tasks import task_discover_listings_at_grid
from ubdc_airbnb.tasks import task_update_calendar


def check_positive(value) -> int:
    value = int(value)
    if value < 0:
        raise ArgumentTypeError(f"{value} must be positive integer.")

    return value


class Command(BaseCommand):
    help = "Import AOI to the database from a shapefile/geojson."

    def add_arguments(self, parser: ArgumentParser):
        subparsers = parser.add_subparsers(
            title="commands",
            description="valid commands",
            help="send a task",
            dest="command",
        )
        subparsers.add_parser("get-calendar")

        discover_listings_cron: ArgumentParser = subparsers.add_parser(
            "discover-listings-cron"
        )
        discover_listings_cron.add_argument(
            "--how-many", dest="how_many", default=100, type=int
        )

        discover_listings: ArgumentParser = subparsers.add_parser(
            "discover-listings"
        )
        discover_listings_arg_group = discover_listings.add_mutually_exclusive_group(
            required=True
        )
        discover_listings_arg_group.add_argument("--grid", dest="target")

        update_grids_cron: ArgumentParser = subparsers.add_parser(
            "update-grids-cron"
        )
        update_grids_cron.add_argument(
            "--how-many", dest="how_many", default=100, type=int
        )
        update_listings_details_cron: ArgumentParser = subparsers.add_parser(
            "update-listing-details-cron"
        )

        update_listings_details_cron.add_argument(
            "--how-many", dest="how_many", default=5000, type=int
        )
        get_calendars_cron: ArgumentParser = subparsers.add_parser(
            "get-calendars-cron"
        )
        get_calendars_cron.add_argument(
            "--how-many", dest="how_many", default=5000, type=int
        )
        get_calendar: ArgumentParser = subparsers.add_parser("get-calendar")
        get_calendar.add_argument(
            "--listing",
            required=True,
            help="listing_id to fetch the calendar for.",
            dest="listing_id",
        )
        get_comments_cron: ArgumentParser = subparsers.add_parser(
            "get-reviews-cron"
        )
        get_comments_cron.add_argument(
            "--how-many", dest="how_many", default=5000, type=int
        )

    def handle(self, *args, **options):
        match options.get("command"):
            case "discover-listings-cron":
                name = op_discover_new_listings_periodical.name
                kwargs = {"how_many": options["how_many"]}
            case "discover-listings":
                name = task_discover_listings_at_grid.name
                kwargs = {
                    "quadkey": options["target"],
                }

            case "update-grids-cron":
                name = op_estimate_listings_or_divide_periodical.name
                kwargs = {"age_hours": 0}

            case "update-listing-details-cron":
                name = op_update_listing_details_periodical.name
                kwargs = {"how_many": options["how_many"]}

            case "get-calendar":
                name = task_update_calendar.name
                kwargs = {"listing_id": options["listing_id"]}

            case "get-calendars-cron":
                name = op_update_calendar_periodical.name
                kwargs = {"how_many": options["how_many"]}

            case "get-reviews-cron":
                name = op_update_reviews_periodical.name
                kwargs = {"how_many": options["how_many"]}

            case "get-booking-quotes-cron":
                name = op_get_booking_detail_periodical.name
                kwargs = {"age_hours": 0}

            case _:
                raise

        result = celery_app.send_task(name=name, kwargs=kwargs)
        self.stdout.write(f"Job submitted with id {result.id}")
