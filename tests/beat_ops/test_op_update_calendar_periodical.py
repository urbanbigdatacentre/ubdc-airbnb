import pytest
from django.core.management import call_command
from faker import Faker

from ..payload_generators import calendar_generator

fake = Faker()


@pytest.mark.django_db(transaction=True)
def test_op_update_calendar_periodical(
    mock_airbnb_client,
    response_queue,
    celery_worker,
    celery_app,
    listings_model,
    ubdcgrid_model,
    ubdctask_model,
    responses_model,
):
    from ubdc_airbnb.operations.calendars import op_update_calendar_periodical

    for prefix_qk in ["03113322331322", "03112322331323"]:
        for idx in range(0, 4):
            qk = prefix_qk + str(idx)
            payload = {
                "content": calendar_generator(),
            }
            response_queue.put(payload)
            call_command("create-test-area", qk)

    grid = ubdcgrid_model.objects.all()
    for idx, g in enumerate(grid):
        centroid = g.geom_3857.centroid
        listing = listings_model.objects.create(listing_id=idx + 1, geom_3857=centroid)

    task = op_update_calendar_periodical.s()
    job = task.apply_async()
    result = job.get()
    assert job.children
    group_results = [c for c in job.children if c.__class__.__name__ == "GroupResult"]
    for g in group_results:
        g.join()  # type: ignore

    assert job.successful()
    assert responses_model.objects.count() == 4 * 2
    assert listings_model.objects.count() == 4 * 2
    for l in listings_model.objects.all():
        assert l.timestamp
        assert l.calendar_updated_at
        assert l.calendar_updated_at > l.timestamp
