import logging

import pytest
from celery.exceptions import TaskRevokedError
from celery.result import AsyncResult

from ubdc_airbnb.tasks import task_debug_sometimes_fail, task_debug_wait

# from . import UBDCBaseTestWorker


@pytest.mark.django_db(transaction=True)
def test_expire(
    celery_app,
    celery_worker,
    caplog,
    listings_model,
):

    caplog.set_level(logging.DEBUG)
    # set a task that expires in 1 second
    from datetime import datetime, timedelta

    from ubdc_airbnb.errors import UBDCRetriableError
    from ubdc_airbnb.models import UBDCTask

    limit = datetime.now() + timedelta(microseconds=1)
    task = task_debug_wait.s(value="Task expired", wait=2, verbose=True).set(expires=0)

    # wait for one second before sending the task

    result: AsyncResult = task.apply_async()
    with pytest.raises(TaskRevokedError):
        rv = result.get()

    obj = UBDCTask.objects.get(task_id=result.task_id)
    assert obj.retries == 0
    assert obj.status == "REVOKED"


# @pytest.mark.skip(reason="This test is not reliable, but it works")
@pytest.mark.django_db(transaction=True)
def test_retry(
    celery_app,
    celery_worker,
):
    from ubdc_airbnb.errors import UBDCRetriableError
    from ubdc_airbnb.models import UBDCTask

    task = task_debug_sometimes_fail.s(fail_percentage=1, verbose=False)

    result: AsyncResult = task.apply_async()
    with pytest.raises(UBDCRetriableError) as exc:
        result.get()
        obj = UBDCTask.objects.get(task_id=result.task_id)
        assert obj.retries == 3


@pytest.mark.django_db(transaction=True)
def test_wait(
    celery_app,
    celery_worker,
):
    from ubdc_airbnb.models import UBDCTask

    task = task_debug_wait.s(value="test", wait=1, verbose=True)
    result: AsyncResult = task.apply_async()

    obj = UBDCTask.objects.get(task_id=result.task_id)
    assert obj.status == "SUBMITTED"
    assert result.get() == "test"

    obj.refresh_from_db()
    assert obj.status == "SUCCESS"
    assert obj.retries == 0
