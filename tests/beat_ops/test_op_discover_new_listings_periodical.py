import pytest
from django.core.management import call_command
from faker import Faker

from ..payload_generators import search_body_generator

fake = Faker()


@pytest.mark.django_db(transaction=True)
def test_op_discover_new_listings_periodical(
    mock_airbnb_client,
    response_queue,
    celery_worker,
    celery_app,
    listings_model,
    ubdcgrid_model,
    ubdctask_model,
    responses_model,
):
    """Test the periodic operation for discovering new listings."""
    from ubdc_airbnb.operations.discovery import op_discover_new_listings_periodical

    for prefix_qk in ["03113322331322", "03112322331323"]:
        for idx in range(0, 4):
            qk = prefix_qk + str(idx)
            payload = {
                "content": search_body_generator(qk=qk),
            }
            response_queue.put(payload)
            call_command("create-test-area", qk)

    grid = ubdcgrid_model.objects.all()
    for idx, g in enumerate(grid):
        centroid = g.geom_3857.centroid
        listing = listings_model.objects.create(listing_id=idx + 1, geom_3857=centroid)

    task = op_discover_new_listings_periodical.s()
    job = task.apply_async()
    result = job.get()
    assert job.children
    group_results = [c for c in job.children if c.__class__.__name__ == "GroupResult"]
    for g in group_results:
        g.join()  # type: ignore

    assert job.successful()
    assert responses_model.objects.count() == 4 * 2
    # 4 initial, 10 per search, 2 areas
    assert listings_model.objects.count() == (4 + 10 * 4) * 2
    for l in listings_model.objects.all():
        assert l.timestamp
        assert l.listing_updated_at is None
        assert l.calendar_updated_at is None
        assert l.listing_updated_at is None
        assert l.reviews_updated_at is None
        assert l.booking_quote_updated_at is None

    for g in ubdcgrid_model.objects.all():
        assert g.timestamp
        assert g.datetime_last_listings_scan
        assert g.datetime_last_listings_scan > g.timestamp
