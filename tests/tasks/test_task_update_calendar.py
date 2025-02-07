import pytest
from .. import payload_generators as pg
from uuid import UUID


# Status code 503 will trigger a UBDCRetriableError.
# If you want to try, feed the response_queue with enough responses or each retry
@pytest.mark.parametrize('status_code', (200, 403))
@pytest.mark.django_db(transaction=True)
def test_task_update_calendar(
        celery_worker,
        celery_app,
        mock_airbnb_client,
        status_code,
        response_queue,
        responses_model
):

    response_queue.put({
        "status_code": status_code,
        "content": pg.calendar_generator()
    })
    from ubdc_airbnb.tasks import task_update_calendar
    from django_celery_results.models import TaskResult

    task = task_update_calendar.s(listing_id=1234567)
    job = task.apply_async()
    result = job.get()

    response = responses_model.objects.first()
    assert response.listing_id == 1234567
    assert response.status_code == status_code
    assert response.ubdc_task_id == UUID(job.id)

    # ubdc task
    task = response.ubdc_task
    assert task
    assert task.task_name == 'ubdc_airbnb.tasks.task_update_calendar'
    assert task.status == 'SUCCESS'

    # celery task
    c_task = TaskResult.objects.get(task_id=job.id)
    assert c_task.status == 'SUCCESS'
    assert c_task.traceback == None
