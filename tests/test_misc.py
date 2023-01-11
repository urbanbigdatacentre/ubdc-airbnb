from datetime import datetime, timedelta

from celery.exceptions import TaskRevokedError
from celery.result import AsyncResult

from ubdc_airbnb.tasks import task_debug_sometimes_fail, task_debug_wait
from . import UBDCBaseTestWorker


class Test(UBDCBaseTestWorker):
    celery_worker_perform_ping_check = True

    def test_wait(self):
        from ubdc_airbnb.models import UBDCTask
        task = task_debug_wait.s(value='test', wait=1, verbose=True)
        result: AsyncResult = task.apply_async()

        obj = UBDCTask.objects.get(task_id=result.task_id)

        assert result.get() == 'test'

    def test_retry(self):
        from ubdc_airbnb.errors import UBDCRetriableError
        from ubdc_airbnb.models import UBDCTask
        task = task_debug_sometimes_fail.s(fail_percentage=1, verbose=False)

        with self.assertRaises(UBDCRetriableError):
            result: AsyncResult = task.apply_async()

            result.get()

        obj = UBDCTask.objects.get(task_id=result.task_id)
        self.assertEquals(obj.retries, 2)
