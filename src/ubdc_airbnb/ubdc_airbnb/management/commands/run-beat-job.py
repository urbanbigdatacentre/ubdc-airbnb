from datetime import datetime

from django.core.management.base import BaseCommand

from . import get_beat_task_by_name, get_beat_tasks

beat_entries = get_beat_tasks()


class Command(BaseCommand):
    help = "Run a Celery Beat Job"

    def add_arguments(self, parser):
        parser.add_argument(
            "job",
            type=str,
            help="The job to run",
            choices=beat_entries,
        )

    def handle(self, *args, **options):

        job_name = options["job"]
        task = get_beat_task_by_name(job_name)
        sig = task.s()

        job = sig.apply_async()
        tick = datetime.now().isoformat()
        self.stdout.write(self.style.SUCCESS(f"{task.name}"))
        self.stdout.write(self.style.SUCCESS(f"{tick} - Sent Celery Beat ( Task {job.id}."))
