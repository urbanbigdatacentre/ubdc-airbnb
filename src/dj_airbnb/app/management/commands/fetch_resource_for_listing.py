from argparse import ArgumentParser, ArgumentTypeError
import concurrent.futures
from typing import Literal

from django.core.management import BaseCommand
from django.db.models import QuerySet

from app.models import UBDCGrid, AOIShape, AirBnBListing
from app.tasks import task_add_listing_detail
from app.tasks import task_update_calendar
from app.tasks import task_update_or_add_reviews_at_listing


def asListing(value) -> int:
    value = int(value)
    try:
        listing = AirBnBListing.objects.get(listing_id=value)
    except AirBnBListing.DoesNotExist:
        raise ArgumentTypeError(f"{value} must be positive integer.")

    return listing


class Command(BaseCommand):
    help = "Fetch a resource for a listing id"

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument('op', choices=['calendar', 'listing-detail', 'reviews'])
        parser.add_argument('listing_id', type=asListing)

    def handle(self, *args, **options):
        listing: AirBnBListing = options['listing_id']
        op: Literal['calendar', 'listing-detail', 'reviews'] = options['op']

        if op == "calendar":
            r = task_update_calendar(listing_id=listing.listing_id)
            return
        if op == "listing-detail":
            r = task_add_listing_detail(listing_id=listing.listing_id)
            return
        if op == "reviews":
            r = task_update_or_add_reviews_at_listing(listing_id=listing.listing_id)
            return
