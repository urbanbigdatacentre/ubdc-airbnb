from django.core.management.base import BaseCommand
from ubdc_airbnb.models import UBDCGrid


class Command(BaseCommand):

    help = 'Add a single quadkey grid. e.g. python manage.py add_quadkey 120210233'

    def add_arguments(self, parser):
        parser.add_argument('quadkey', type=str, help='Quadkey of the grid to add')

    def handle(self, *args, **kwargs):
        quadkey = kwargs['quadkey']
        grid = UBDCGrid.objects.create_from_quadkey(quadkey=quadkey)

        self.stdout.write(self.style.SUCCESS(f'Successfully added grid with quadkey: {quadkey}'))
