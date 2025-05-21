from django.core.management.base import BaseCommand

from . import int_to_aoi


class Command(BaseCommand):
    help = "Edit collection attributes of an Area of Interest (AOI)"

    def add_arguments(self, parser):
        # Required argument for AOI primary key
        parser.add_argument("pk", type=int_to_aoi, help="Primary key of the AOI to edit")
        parser.add_argument("--delete", action="store_true", help="Delete the AOI")

        # Optional arguments for collection attributes
        collect_calendar_group = parser.add_mutually_exclusive_group(required=False)
        collect_calendar_group.add_argument("--calendars", action="store_true", help="Set collect flag to True")
        collect_calendar_group.add_argument("--no-calendars", action="store_true", help="Set collect flag to False")

        collect_listing_details_group = parser.add_mutually_exclusive_group(required=False)
        collect_listing_details_group.add_argument(
            "--listing-details", action="store_true", help="Set collect listing-details"
        )
        collect_listing_details_group.add_argument(
            "--no-listing-details", action="store_true", help="Don't collect listing details"
        )

    def handle(self, *args, **options):
        aoi = options["pk"]

        # TODO: Create test cases for --delete flag
        if options["delete"]:
            aoi.delete()
            self.stdout.write(self.style.SUCCESS(f"Successfully deleted AOI {aoi.pk}"))
            return

        # Process the collect calendars flag
        if options["calendars"]:
            aoi.collect_calendars = True
            self.stdout.write(f"Setting collect_calendars to True for AOI {aoi.pk}")
        elif options["no_calendars"]:
            aoi.collect_calendars = False
            self.stdout.write(f"Setting collect_calendars to False for AOI {aoi.pk}")

        # Process the collect listing details flag
        if options["listing_details"]:
            aoi.collect_listing_details = True
            self.stdout.write(f"Setting collect_listing_details to True for AOI {aoi.pk}")
        elif options["no_listing_details"]:
            aoi.collect_listing_details = False
            self.stdout.write(f"Setting collect_listing_details to False for AOI {aoi.pk}")

        # Save the AOI
        aoi.save()
        self.stdout.write(self.style.SUCCESS(f"Successfully updated AOI {aoi.pk}"))
