from argparse import ArgumentParser

from django.core.management import BaseCommand

from ubdc_airbnb.management.commands import int_to_listing
from ubdc_airbnb.models import AirBnBListing
from ubdc_airbnb.tasks import (
    task_add_reviews_of_listing,
    task_get_listing_details,
    task_update_calendar,
)

op_choices = [
    # get calendar data for a listing
    "calendar",
    # get listing details for a listing
    "listing-detail",
    # get reviews for a listing
    "reviews",
]


class Command(BaseCommand):
    help = """
    Get Airbnb data for a listing id. The listing must have been previously registered through a scan.
    
    example: python manage.py get-for-listing-id calendar 123456
    """

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument("op", choices=op_choices)
        parser.add_argument("listing_id", type=int_to_listing)

    def handle(self, *args, **options):
        as_task = options.get("as-task", False)
        listing: AirBnBListing = options["listing_id"]
        op = options["op"]

        if op == "calendar":
            r = task_update_calendar(listing_id=listing.listing_id)
            self.stdout.write(f"Fetched calendar for listing {r}")
            return
        if op == "listing-detail":
            r = task_get_listing_details(listing_id=listing.listing_id)
            self.stdout.write(f"Fetched listing-details for listing {r}")
            return
        if op == "reviews":
            r = task_add_reviews_of_listing(listing_id=listing.listing_id)
            self.stdout.write(f"Fetched reviews for listing {r}")
            return

        print("Done!")
