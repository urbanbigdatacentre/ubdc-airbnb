from core.celery import app
from django.core.management.base import BaseCommand

beat_entries: dict = app.conf.beat_schedule
jobs = list(x.split(".")[-1] for x in beat_entries.keys())


class Command(BaseCommand):
    help = "Run a Celery Beat Job"

    def add_arguments(self, parser):
        parser.add_argument(
            "job",
            type=str,
            help="The job to run",
            choices=jobs,
        )

    def handle(self, *args, **options):
        import importlib

        fqn_candidates = list(filter(lambda x: x["task"].endswith(options["job"]), beat_entries.values()))
        assert len(fqn_candidates) == 1, f"Job {options['job']} is not registered in the beat schedule."
        fqn_str = fqn_candidates[0]["task"]
        module = fqn_str.rsplit(".", 1)[0]
        job_str = fqn_str.split(".")[-1]
        mod = importlib.import_module(module)
        job = getattr(mod, job_str)
        task = job.s()
        result = task.apply_async()
        self.stdout.write(self.style.SUCCESS(f"Sent Celery Beat Task {result.id}."))
