from argparse import ArgumentParser

from django.core.management import BaseCommand

from ubdc_airbnb.management.commands import int_to_listing
from ubdc_airbnb.models import AirBnBListing
from ubdc_airbnb.tasks import (
    task_get_listing_details,
    task_update_calendar,
    task_update_or_add_reviews_at_listing,
)

op_choices = ["calendar", "listing-detail", "reviews"]


class Command(BaseCommand):
    help = "Fetch a resource for a listing id"

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument("op", choices=op_choices)
        parser.add_argument("listing_id", type=int_to_listing)
        parser.add_argument(
            "--as-task",
            dest="as-task",
            action="store_true",
            help="Run as a task.",
        )

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
            r = task_update_or_add_reviews_at_listing(listing_id=listing.listing_id)
            self.stdout.write(f"Fetched reviews for listing {r}")
            return

        print("Done!")
