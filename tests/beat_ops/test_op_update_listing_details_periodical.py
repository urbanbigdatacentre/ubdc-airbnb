import pytest
from django.core.management import call_command
from faker import Faker

from ..payload_generators import listing_details_generator

fake = Faker()


@pytest.mark.django_db(transaction=True)
def test_op_update_listing_details_periodical(
    mock_airbnb_client,
    response_queue,
    celery_worker,
    celery_app,
    listings_model,
    ubdcgrid_model,
    ubdctask_model,
    responses_model,
):
    """Test the periodic operation for updating listing details."""
    from ubdc_airbnb.operations.listing_details import (
        op_update_listing_details_periodical,
    )

    for idx in range(0, 4):
        payload = {
            "content": listing_details_generator(),
        }
        response_queue.put(payload)
        call_command("create-test-area", "03113322331322" + str(idx))

    grid = ubdcgrid_model.objects.all()
    for idx, g in enumerate(grid):
        centroid = g.geom_3857.centroid
        listing = listings_model.objects.create(listing_id=idx + 1, geom_3857=centroid)

    task = op_update_listing_details_periodical.s()
    job = task.apply_async()
    result = job.get()
    assert job.children
    group_results = [c for c in job.children if c.__class__.__name__ == "GroupResult"]
    for g in group_results:
        g.join()  # type: ignore

    assert job.successful()
    assert responses_model.objects.count() == 4
