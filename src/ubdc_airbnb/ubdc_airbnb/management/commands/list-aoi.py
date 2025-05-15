import csv
import sys
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils.formats import date_format

from ubdc_airbnb.models import AOIShape


class Command(BaseCommand):
    help = """
    List Areas-Of-Interest (AOIs) registered in the system.
    Displays AOIs in a sequential format in the terminal.
    Can also export the list as CSV with the --csv option.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            action="store_true",
            help="Export AOI list as CSV to stdout",
        )
        parser.add_argument(
            "--output",
            type=str,
            help="Specify file to save CSV output (implies --csv)",
        )
        parser.add_argument(
            "--filter",
            type=str,
            help="Filter AOIs by name (case-insensitive)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limit the number of AOIs displayed (0 for no limit)",
        )

    def handle(self, *args, **options):
        # Start with all AOIs
        queryset = AOIShape.objects.all().order_by("name")

        # Apply filtering if specified
        if options["filter"]:
            queryset = queryset.filter(name__icontains=options["filter"])

        # Apply limit if specified and greater than 0
        if options["limit"] > 0:
            queryset = queryset[: options["limit"]]

        # Get count of AOIs found
        aoi_count = queryset.count()

        # Determine output mode (CSV or terminal display)
        if options["csv"] or options["output"]:
            self._output_csv(queryset, options["output"])
        else:
            self._output_terminal(queryset, aoi_count)

    def _output_terminal(self, queryset, count):
        """Display AOIs in a formatted table in the terminal."""
        if count == 0:
            self.stdout.write(self.style.WARNING("No AOIs found."))
            return

        # Print header
        self.stdout.write(self.style.SUCCESS(f"Found {count} AOI(s):"))
        self.stdout.write("-" * 80)

        # Format headers
        headers = ["ID", "Name", "Created", "User", "Notes"]
        header_format = "{:<5} {:<30} {:<19} {:<15} {:<30}"
        self.stdout.write(self.style.SUCCESS(header_format.format(*headers)))
        self.stdout.write("-" * 80)

        # Format and print each AOI
        row_format = "{:<5} {:<30} {:<19} {:<15} {:<30}"
        for aoi in queryset:
            # Extract notes information
            user = aoi.notes.get("user", "unknown") if aoi.notes else "unknown"
            notes_str = f"Path: {aoi.notes.get('path', 'N/A')}" if aoi.notes else "N/A"

            # Format dates
            created = date_format(aoi.timestamp, "Y-m-d H:i:s")

            # Format row
            row = [
                aoi.id,
                aoi.name[:28] + "..." if len(aoi.name) > 30 else aoi.name,
                created,
                user[:13] + "..." if len(user) > 15 else user,
                notes_str[:28] + "..." if len(notes_str) > 30 else notes_str,
            ]

            self.stdout.write(row_format.format(*row))

        self.stdout.write("-" * 80)

    def _output_csv(self, queryset, output_file):
        """Export AOIs as CSV to stdout or a file."""
        # Prepare fieldnames for CSV
        fieldnames = ["id", "name", "created_at", "user", "path", "file_name", "import_date"]

        # Open file or use stdout
        if output_file:
            file_handle = open(output_file, "w", newline="")
            self.stdout.write(self.style.SUCCESS(f"Exporting AOIs to {output_file}"))
        else:
            file_handle = sys.stdout

        try:
            # Create CSV writer
            writer = csv.DictWriter(file_handle, fieldnames=fieldnames)
            writer.writeheader()

            # Write rows
            for aoi in queryset:
                # Extract notes data safely
                notes = aoi.notes or {}

                writer.writerow(
                    {
                        "id": aoi.id,
                        "name": aoi.name,
                        "created_at": aoi.timestamp.isoformat(),
                        "user": notes.get("user", ""),
                        "path": notes.get("path", ""),
                        "file_name": notes.get("name", ""),
                        "import_date": notes.get("import_date", ""),
                    }
                )
        finally:
            # Close file if it's not stdout
            if output_file and file_handle is not sys.stdout:
                file_handle.close()
                self.stdout.write(self.style.SUCCESS(f"CSV export complete: {output_file}"))
