from datetime import timedelta

from celery import Task
from celery.utils.log import get_task_logger
from django.utils import timezone
from dotenv import load_dotenv
from requests.exceptions import HTTPError, ProxyError

from app.errors import UBDCRetriableError
from app.models import UBDCTask

load_dotenv()

logger = get_task_logger(__name__)


def delta_time(hours=24):
    return timezone.now() + timedelta(hours=hours)


# noinspection PyAbstractClass
# AbstractMethod: run() is patched by __call__ in run time (?)
# no need to re-implement it
class BaseTaskWithRetry(Task):
    autoretry_for = (UBDCRetriableError, ProxyError)
    retry_kwargs = {'max_retries': 2}
    retry_backoff = 1  # * 60  # 1 min
    retry_backoff_max = 30  # * 60  # 30 min
    retry_jitter = True
    # it's overridden by  CELERY_TASK_DEFAULT_RATE_LIMIT
    rate_limit = '10/m'
    acks_late = True
    worker_prefetch_multiplier = 1

    def __call__(self, *args, **kwargs):
        task_id = self.request.id
        if task_id is None:
            # The task was called directly
            return self.run(*args, **kwargs)

        # RACE CONDITIONS:
        # Before each task is send to the broker for consumption, meta are written into the database,
        # so it should be an entry with that task_id.
        # Exception is it's 'eager' which then the task is applied locally

        if not self.request.is_eager and (self.name.startswith('app') or self.name.startswith('dj_airbnb')):

            ubdc_task_entry_qs = UBDCTask.objects.select_related('group_task').filter(task_id=task_id)

            if ubdc_task_entry_qs.exists():
                ubdc_task_entry = ubdc_task_entry_qs.first()
                dt_now = timezone.now()
                ubdc_task_entry.datetime_started = dt_now
                ubdc_task_entry.status = ubdc_task_entry.TaskTypeChoices.STARTED

                group_task = ubdc_task_entry.group_task
                if group_task and group_task.datetime_started is None:
                    group_task.datetime_started = dt_now
                    group_task.save()
                ubdc_task_entry.save()

        return self.run(*args, **kwargs)

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """Handler called after the task returns."""
        # try:
        #     ubdc_task_entry = UBDCTask.objects.select_related('group_task').get(task_id=task_id)
        #
        #     group_task = ubdc_task_entry.group_task
        #     if group_task and group_task.all_finished:
        #         group_task.datetime_finished = timezone.now()
        #         group_task.save()
        #
        # except UBDCTask.DoesNotExist:
        return

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """ This is run by the worker when the task fails."""
        try:
            ubdc_taskentry = UBDCTask.objects.get(task_id=task_id)
        except UBDCTask.DoesNotExist:
            return
        ubdc_taskentry.datetime_finished = timezone.now()
        ubdc_taskentry.status = ubdc_taskentry.TaskTypeChoices.FAILURE
        ubdc_taskentry.save()

    def on_success(self, retval, task_id, args, kwargs):
        """Run by the worker if the task executes successfully."""
        try:
            ubdc_task_entry = UBDCTask.objects.get(task_id=task_id)
        except UBDCTask.DoesNotExist:
            return

        ubdc_task_entry.datetime_finished = timezone.now()
        try:
            ubdc_task_entry.time_to_complete = \
                (ubdc_task_entry.datetime_finished - ubdc_task_entry.datetime_started).__str__()
        except:
            ubdc_task_entry.time_to_complete = None

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
