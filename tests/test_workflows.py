import pytest
from celery.result import GroupResult
from mercantile import Tile, bounds, neighbors, quadkey_to_tile


@pytest.mark.parametrize("scan_for_new_listings", [True, False])
@pytest.mark.django_db(transaction=True)
def test_op_discover_new_listings_periodical(
    ubdcgrid_model,
    aoishape_model,
    mock_airbnb_client,
    celery_worker,
    celery_app,
    scan_for_new_listings,
):

    aoi_bounds = bounds(quadkey_to_tile("12210000030"))
    bbox = aoi_bounds.west, aoi_bounds.south, aoi_bounds.east, aoi_bounds.north
    aoi = aoishape_model.create_from_bbox(name="test", bbox=bbox)
    aoi.scan_for_new_listings = scan_for_new_listings
    aoi.save()
    init_tile = quadkey_to_tile("12210000030300")
    neighbors_tiles = neighbors(init_tile)
    all_tiles = [init_tile] + neighbors_tiles

    for t in all_tiles:
        ubdcgrid_model.objects.create_from_tile(t)

    assert ubdcgrid_model.objects.count() == 9

    # actual test starts from here.

    from ubdc_airbnb.operations.discovery import op_discover_new_listings_periodical

    job = op_discover_new_listings_periodical.s()
    group_task = job.apply_async()
    group_result_id = group_task.get(timeout=600)
    if group_result_id is not None:
        group_result = GroupResult.restore(group_result_id)  # type: ignore

        group_result.join()
        assert group_result.completed_count() == 9
        assert ubdcgrid_model.objects.count() == 18
        # the first 3 results are spawning 4 new subtasks
        assert len(group_result[0].children[0]) == 4
        assert len(group_result[1].children[0]) == 4
        assert len(group_result[2].children[0]) == 4
