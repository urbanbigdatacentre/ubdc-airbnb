from argparse import ArgumentParser

from django.core.management import BaseCommand

from ubdc_airbnb.management.commands import int_to_listing
from ubdc_airbnb.models import AirBnBListing
from ubdc_airbnb.tasks import task_add_listing_detail
from ubdc_airbnb.tasks import task_update_calendar
from ubdc_airbnb.tasks import task_update_or_add_reviews_at_listing


class Command(BaseCommand):
    help = "Fetch a resource for a listing id"

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument('op', choices=['calendar', 'listing-detail', 'reviews'])
        parser.add_argument('listing_id', type=int_to_listing)

    def handle(self, *args, **options):
        listing: AirBnBListing = options['listing_id']
        op = options['op']

        if op == "calendar":
            r = task_update_calendar(listing_id=listing.listing_id)
            self.stdout.write(f'Fetched calendar for listing {r}')
            return
        if op == "listing-detail":
            r = task_add_listing_detail(listing_id=listing.listing_id)
            self.stdout.write(f'Fetched listing-details for listing {r}')
            return
        if op == "reviews":
            r = task_update_or_add_reviews_at_listing(listing_id=listing.listing_id)
            self.stdout.write(f'Fetched reviews for listing {r}')
            return

        print('Done!')
