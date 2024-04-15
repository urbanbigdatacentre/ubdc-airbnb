import pytest

# https://labs.mapbox.com/what-the-tile/
test_quadkey = "0311332233311"  # glasgow city centre
methil_quadkey = "031133231323"  # methil, fife. Falls withing a qk, and doesn't many listings

TASK_TIMEOUT = 10 * 60  # 10 minutes


@pytest.mark.django_db(transaction=True)
def test_get_search_at_grid_metadata(
    mock_airbnb_client,
    listings_model,
    celery_worker,
    celery_app,
    responses_model,
    ubdcgrid_model,
):
    from ubdc_airbnb.tasks import task_discover_listings_at_grid

    ubdcgrid_model.objects.create_from_quadkey(quadkey=test_quadkey, save=True)
    assert ubdcgrid_model.objects.count() == 1

    task = task_discover_listings_at_grid.s(quadkey=test_quadkey)
    result = task.apply_async()

    result.get(timeout=TASK_TIMEOUT)


@pytest.mark.parametrize(
    "quadkey",
    (
        [
            methil_quadkey,
        ]
    ),
)
@pytest.mark.django_db(transaction=True)
def test_get_listings_at_grid(
    quadkey,
    # mock_airbnb_client,
    celery_worker,
    celery_app,
    listings_model,
    responses_model,
    ubdcgrid_model,
):
    from ubdc_airbnb.tasks import task_register_listings_or_divide_at_quadkey

    initial_count = listings_model.objects.count()
    grid = ubdcgrid_model.objects.create_from_quadkey(quadkey=quadkey, save=True)
    assert ubdcgrid_model.objects.count() == 1

    task = task_register_listings_or_divide_at_quadkey.s(quadkey=quadkey)
    result = task.apply_async()

    result.get(timeout=TASK_TIMEOUT)

    assert listings_model.objects.count() > initial_count
    grid.refresh_from_db()
    assert grid.estimated_listings == listings_model.objects.count() - initial_count
