from django.core.management import BaseCommand
from app.tasks import task_tidy_grids


class Command(BaseCommand):

    def handle(self, *args, **options):
        task_tidy_grids(less_than=50)
