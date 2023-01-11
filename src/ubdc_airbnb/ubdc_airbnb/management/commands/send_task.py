import os
import sysconfig
from argparse import ArgumentParser, ArgumentTypeError
from pathlib import Path

from django.core.management.base import BaseCommand

from app.operations import (op_discover_new_listings_periodical,
                            op_estimate_listings_or_divide_periodical,
                            op_update_listing_details_periodical, op_update_calendar_periodical,
                            op_update_reviews_periodical, op_get_booking_detail_periodical)
from core.celery import app as celery_app

os.environ.setdefault(
    "PROJ_LIB", os.getenv('PROJ_LIB') or Path(
        Path(sysconfig.get_paths()["purelib"]) / r"osgeo/data/proj"
    ).as_posix())


def check_positive(value) -> int:
    value = int(value)
    if value < 0:
        raise ArgumentTypeError(f"{value} must be positive integer.")

    return value


class Command(BaseCommand):
    help = 'Import AOI to the database from a shapefile/geojson.'

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument("--ignore-activated-aoi", action="store_true")
        subparsers = parser.add_subparsers(title='commands', description='valid commands',
                                           help='send a task manually', dest='command')
        find_listings: ArgumentParser = subparsers.add_parser('discover-listings')
        update_grids: ArgumentParser = subparsers.add_parser('update-grids')
        update_listings: ArgumentParser = subparsers.add_parser('get-listing-details')
        get_calendars: ArgumentParser = subparsers.add_parser('get-calendars')
        get_comments: ArgumentParser = subparsers.add_parser('get-reviews')

    def handle(self, *args, **options):
        if options.get('command') == 'discover-listings':
            result = celery_app.send_task(name=op_discover_new_listings_periodical.name, age_hours=0)
            self.stdout.write(f"Job submitted with id {result.id}")
        if options.get('command') == 'update-grids':
            name = op_estimate_listings_or_divide_periodical.name
            result = celery_app.send_task(name=name, age_hours=0)
            self.stdout.write(f"Job {name} submitted with id {result.id}")
        if options.get('command') == 'get-listing-details':
            name = op_update_listing_details_periodical.name
            result = celery_app.send_task(name=name, age_hours=0)
            self.stdout.write(f"Job {name} submitted with id {result.id}")
        if options.get('command') == 'get-calendars':
            name = op_update_calendar_periodical.name
            result = celery_app.send_task(name=name, age_hours=0)
            self.stdout.write(f"Job {name} submitted with id {result.id}")
        if options.get('command') == 'get-reviews':
            name = op_update_reviews_periodical.name
            result = celery_app.send_task(name=name, age_hours=0)
            self.stdout.write(f"Job {name} submitted with id {result.id}")
        if options.get('command') == 'get-booking-quotes':
            name = op_get_booking_detail_periodical.name
            result = celery_app.send_task(name=name, age_hours=0)
            self.stdout.write(f"Job {name} submitted with id {result.id}")
