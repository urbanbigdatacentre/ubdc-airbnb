from argparse import ArgumentParser

from django.core.management import BaseCommand

from ubdc_airbnb.management.commands import int_to_listing
from ubdc_airbnb.models import AirBnBListing
from ubdc_airbnb.tasks import task_get_listing_details, task_update_calendar


class Command(BaseCommand):
    help = """
    Get Airbnb data for a listing id. The listing must have been previously registered through a scan.

    example: python manage.py get-for-listing-id calendar 123456
    """

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument("--listing-id", type=int_to_listing, required=True)
        operation = parser.add_mutually_exclusive_group(required=True)
        operation.add_argument("--calendar", action="store_true")
        operation.add_argument("--listing-detail", action="store_true")

    def handle(self, *args, **options):
        listing: AirBnBListing = options["listing_id"]
        get_calendar: bool = options["calendar"]
        get_listing_detail: bool = options["listing_detail"]

        if get_calendar:
            r = task_update_calendar(listing_id=listing.listing_id)  # type: ignore
            self.stdout.write(f"Fetched calendar for listing {listing.listing_id}")

        if get_listing_detail:
            r = task_get_listing_details(listing_id=listing.listing_id)  # type: ignore
            self.stdout.write(f"Fetched listing-details for listing {listing.listing_id}")
            return

        self.stdout.write(self.style.SUCCESS("Done!"))
