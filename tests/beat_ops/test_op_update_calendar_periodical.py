import pytest
from django.core.management import call_command
from faker import Faker

from ..payload_generators import calendar_generator

fake = Faker()


@pytest.mark.parametrize("status_code", [200, 403])
@pytest.mark.parametrize("params", [{}, {"stale": True}], ids=["cli_param_none", "cli_param_stale"])
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
    status_code,
    params
):
    from ubdc_airbnb.operations.calendars import op_update_calendar_periodical
    from ubdc_airbnb.utils.time import start_of_day
    start_date = start_of_day()

    for prefix_qk in ["03113322331322", "03112322331323"]:
        for idx in range(0, 4):
            qk = prefix_qk + str(idx)
            payload = {
                "status_code": status_code,
                "content": calendar_generator(),
            }
            response_queue.put(payload)
            call_command("create-test-area", qk)

    grid = ubdcgrid_model.objects.all()
    for idx, g in enumerate(grid):
        centroid = g.geom_3857.centroid
        listing = listings_model.objects.create(
            listing_id=idx + 1,
            geom_3857=centroid,
            calendar_updated_at=fake.date_time_between(
                start_date=start_date, end_date='-10m') if idx % 2 == 0 else None,
        )

    task = op_update_calendar_periodical.s(**params)
    job = task.apply_async()
    result = job.get()
    assert job.children
    group_results = [c for c in job.children if c.__class__.__name__ == "GroupResult"]
    for g in group_results:
        g.join()  # type: ignore

    expected_actions = 4 if params == 'stale' else 8

    assert job.successful()
    assert responses_model.objects.count() == expected_actions
    assert listings_model.objects.count() == 4 * 2
    assert ubdctask_model.objects.filter().count() == expected_actions + 1
    for l in listings_model.objects.all():
        assert l.timestamp
        assert l.calendar_updated_at
        assert l.calendar_updated_at > start_date
