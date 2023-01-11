import json
import os
import sysconfig
from argparse import ArgumentParser, ArgumentTypeError
from pathlib import Path
from pprint import pprint

from django.core.management.base import BaseCommand

from ubdc_airbnb.models import AirBnBResponse, AirBnBResponseTypes, AirBnBListing, AirBnBUser

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
        subparsers = parser.add_subparsers(title='subcommands', description='valid subcommands',
                                           help='sub-command help', dest='command')
        parser_get_calendar: ArgumentParser = subparsers.add_parser('calendar', help='get the calendar for a listing')
        parser_get_details: ArgumentParser = subparsers.add_parser('listing-detail',
                                                                   help='get the listing Details for a listing')
        parser_get_booking_quote: ArgumentParser = subparsers.add_parser('booking-quote',
                                                                         help='get a Booking Quote for a listing')
        parser_get_user: ArgumentParser = subparsers.add_parser('user-detail', help='get the User',
                                                                description='Get user details form the Database for user with USER_ID.\n'
                                                                            'If the user does not exist it will be fetched from airbnb.\n'
                                                                            ' TODO: --refresh')
        parser_get_calendar.add_argument('listing_id', type=check_positive, help="listing_id")
        parser_get_details.add_argument('listing_id', type=check_positive, help="listing_id")
        parser_get_booking_quote.add_argument('listing_id', type=check_positive, help="listing_id")
        parser_get_user.add_argument('user_id', type=check_positive, help="user_id")

    def handle(self, *args, **options):
        error = {"error": None, "msg": None}
        try:
            if options.get('command') == 'calendar':
                from ubdc_airbnb.tasks import task_update_calendar
                listing_id = task_update_calendar(options.get('listing_id'))
                response = AirBnBResponse.objects.filter(listing_id=listing_id,
                                                         _type=AirBnBResponseTypes.calendar).order_by(
                    "timestamp").first()
                self.stdout.write(json.dumps(response.payload, indent=4, sort_keys=True))

            if options.get('command') == 'listing-detail':
                from ubdc_airbnb.tasks import task_add_listing_detail
                listing_id = task_add_listing_detail(options.get('listing_id'))
                response = AirBnBListing.responses.objects.filter(listing_id=listing_id,
                                                                  _type=AirBnBResponseTypes.listingDetail).order_by(
                    "timestamp").first()

                self.stdout.write(json.dumps(response.payload, indent=4, sort_keys=True))

            if options.get('command') == 'user-detail':
                from ubdc_airbnb.tasks import task_get_or_create_user, task_update_user_details

                user_id = task_get_or_create_user(user_id=options.get('user_id'), defer=False)
                user_obj = AirBnBUser.objects.filter(user_id=user_id).first()
                response = user_obj.responses.order_by('timestamp').first()

                self.stdout.write(json.dumps(response.payload, indent=4, sort_keys=True))

            if options.get('command') == 'booking-quote':
                from ubdc_airbnb.tasks import task_update_calendar, task_get_booking_detail
                listing_id = options.get('listing_id')
                # listing_id = task_update_calendar(listing_id)
                listing_id = task_get_booking_detail(listing_id=listing_id)
                listing_obj = AirBnBListing.objects.get(listing_id=listing_id)

                booking_response = listing_obj.responses.filter(_type=AirBnBResponseTypes.bookingQuote).order_by(
                    "timestamp").first()
                self.stdout.write(json.dumps(booking_response.payload, indent=4, sort_keys=True))

        except AirBnBResponse.DoesNotExist as exc:
            error['error'] = "ResponseError"
            error['msg'] = f"{exc}"
            self.stdout.write(pprint(error))
        except AirBnBListing.DoesNotExist as exc:
            error['error'] = "ResponseError"
            error['msg'] = f"{exc}"
            self.stdout.write(pprint(error))
