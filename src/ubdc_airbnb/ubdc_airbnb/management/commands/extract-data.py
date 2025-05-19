from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Description of what this command does"

    def add_arguments(self, parser):
        operation = parser.add_mutually_exclusive_group(required=True)
        operation.add_argument(
            "--calendar",
            action="store_true",
            help="Extract calendar data",
        )
        operation.add_argument(
            "--listing-detail",
            action="store_true",
            help="Extract listing detail data",
        )

        time_boundaries = parser.add_argument_group()

    def handle(self, *args, **options):
        try:
            # Your command logic goes here
            self.stdout.write(self.style.SUCCESS("Command completed successfully"))
        except Exception as e:
            raise CommandError(f"An error occurred: {str(e)}")
