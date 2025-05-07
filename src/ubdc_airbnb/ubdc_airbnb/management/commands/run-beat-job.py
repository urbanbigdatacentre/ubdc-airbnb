from datetime import datetime

from django.core.management.base import BaseCommand
from more_itertools import collapse

from . import get_beat_task_by_name, get_beat_tasks

beat_entries = get_beat_tasks()


def kv_arg(arg):
    if "=" in arg:
        k, v = arg.split("=")
        return {k: v}
    else:
        return {}


class Command(BaseCommand):
    help = "Run a Celery Beat Job"

    def add_arguments(self, parser):
        parser.add_argument(
            "--arg",
            nargs="*",
            type=kv_arg,
            action="append",
            default=[],
            required=False,
            help="Run the job with these arguments",
        )

        parser.add_argument(
            "job",
            type=str,
            help="The job to run",
            choices=beat_entries,
        )

    def handle(self, *args, **options):

        job_kwargs = {}
        job_name = options["job"]
        args = options.get("arg") or []

        for arg in collapse(options.get("arg", []), levels=1):
            job_kwargs.update(**arg)

        task = get_beat_task_by_name(job_name)
        sig = task.s(**job_kwargs)

        job = sig.apply_async()
        tick = datetime.now().isoformat()
        self.stdout.write(self.style.SUCCESS(f"{task.name}"))
        self.stdout.write(self.style.SUCCESS(f"{tick} - Sent Celery Beat ( Task {job.id}."))
