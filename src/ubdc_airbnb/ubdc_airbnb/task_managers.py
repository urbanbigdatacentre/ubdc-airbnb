from datetime import timedelta

from celery import Task
from celery.exceptions import TaskRevokedError
from celery.utils.log import get_task_logger
from django.utils import timezone
from requests.exceptions import ProxyError

from ubdc_airbnb.errors import UBDCResourceIsNotAvailable, UBDCRetriableError
from ubdc_airbnb.models import UBDCTask

logger = get_task_logger(__name__)


def delta_time(hours=24):
    return timezone.now() + timedelta(hours=hours)


# noinspection PyAbstractClass
# AbstractMethod: run() is patched by __call__ in run time (?)
# no need to re-implement it
class BaseTaskWithRetry(Task):
    autoretry_for = (UBDCRetriableError, ProxyError)
    retry_kwargs = {"max_retries": 2}  # initial retry + 2 retries = 3 attempts
    retry_backoff = True
    retry_backoff_max = 30  # seconds
    retry_jitter = False
    acks_late = False
    worker_prefetch_multiplier = 1

    def __call__(self, *args, **kwargs):
        task_id = self.request.id
        if task_id is None:
            # The task was called directly
            return self.run(*args, **kwargs)

        # RACE CONDITIONS:
        # Before each task is send to the broker for consumption, meta are written into the database.
        # There should be an entry with that task_id.

        # An Exception could be risen if the tasak is 'eager' in  which case then the task is applied locally

        if not self.request.is_eager and (self.name.startswith("ubdc_airbnb") or self.name.startswith("ubdc_airbnb")):
            ubdc_task_entry_qs = UBDCTask.objects.select_related("group_task").filter(task_id=task_id)

            ubdc_task_entry = ubdc_task_entry_qs.first()
            if ubdc_task_entry:
                dt_now = timezone.now()
                if ubdc_task_entry.datetime_started is None:
                    ubdc_task_entry.datetime_started = dt_now

                ubdc_task_entry.status = ubdc_task_entry.TaskTypeChoices.STARTED

                group_task = ubdc_task_entry.group_task
                if group_task and group_task.datetime_started is None:
                    group_task.datetime_started = dt_now
                    group_task.save()
                ubdc_task_entry.save()

        return self.run(*args, **kwargs)

    def before_start(self, task_id, args, kwargs):
        "Run by the worker before the task starts executing., The return value of this handler is ignored."
        return

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """Handler called after the task returns."""
        return

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """This is run by the worker when the task fails."""
        try:
            ubdc_taskentry = UBDCTask.objects.get(task_id=task_id)
        except UBDCTask.DoesNotExist:
            logger.warning(f"Task {task_id} was not found on database")
            return
        ubdc_taskentry.datetime_finished = timezone.now()
        ubdc_taskentry.status = ubdc_taskentry.TaskTypeChoices.FAILURE
        if isinstance(exc, UBDCResourceIsNotAvailable):
            # The resource is not available, so we have succefully probe it
            ubdc_taskentry.status = ubdc_taskentry.TaskTypeChoices.SUCCESS
        if isinstance(exc, TaskRevokedError):
            ubdc_taskentry.status = ubdc_taskentry.TaskTypeChoices.REVOKED
        ubdc_taskentry.save()

    def on_success(self, retval, task_id, args, kwargs):
        """Run by the worker if the task executes successfully."""
        try:
            ubdc_task_entry = UBDCTask.objects.get(task_id=task_id)
        except UBDCTask.DoesNotExist:
            return

        ubdc_task_entry.datetime_finished = timezone.now()
        try:
            started = ubdc_task_entry.datetime_started or timezone.now()
            finished = ubdc_task_entry.datetime_finished
            dt = finished - started
            ubdc_task_entry.time_to_complete = str(dt)
        except:
            ubdc_task_entry.time_to_complete = ""

        ubdc_task_entry.status = ubdc_task_entry.TaskTypeChoices.SUCCESS
        ubdc_task_entry.save()

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """This is run by the worker when the task is to be retried."""
        try:
            ubdc_task_entry = UBDCTask.objects.get(task_id=task_id)
        except UBDCTask.DoesNotExist:
            return
        ubdc_task_entry.status = ubdc_task_entry.TaskTypeChoices.RETRY
        ubdc_task_entry.retries += 1
        ubdc_task_entry.save()
