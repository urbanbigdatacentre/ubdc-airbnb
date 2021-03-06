from celery.result import AsyncResult
from . import UBDCBaseTestWorker
from app.tasks import task_get_or_create_user
from ..models import AirBnBUser, UBDCTask


class TestGridOps(UBDCBaseTestWorker):
    user_id = '141986833'  # me

    def test_get_or_create_user_defer(self):
        task = task_get_or_create_user.s(user_id=self.user_id)
        job = task.apply_async()
        childs = list(job.collect())
        user = AirBnBUser.objects.get(user_id=job.result)

        tasks = UBDCTask.objects.filter(task_name__contains='task_get_or_create_user').first()
        result = AsyncResult(tasks.task_id)
        self.assertIsNotNone(user)
