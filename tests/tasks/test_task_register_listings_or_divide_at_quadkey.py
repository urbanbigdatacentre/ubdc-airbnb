from collections import namedtuple

import pytest

from .. import payload_generators as pg

# https://labs.mapbox.com/what-the-tile/
test_quadkey = "0311332233311"  # glasgow city centre
methil_quadkey = "031133231323"  # methil, fife.
a_long_qk = "031133231323031133231323"  # 24 characters long

TASK_TIMEOUT = 10 * 60  # 10 minutes


@pytest.mark.parametrize(
    "quadkey,responses,expected_grids",
    (
        # emulate a normal quadkey, which has 1 page of results.
        [methil_quadkey, [pg.search_body_generator(methil_quadkey, has_next_page=False)], 1],
        # emulate a long quadkey, which has 3 pages of results.
        [
            a_long_qk,
            [
                # fmt: off
            pg.search_body_generator(qk=a_long_qk, has_next_page=True),
            pg.search_body_generator(qk=a_long_qk, has_next_page=True),
            pg.search_body_generator(qk=a_long_qk, has_next_page=False),
                # fmt: on
            ],
            1,
        ],
        # emulate a normal quadkey that is being split into 4 sub-grids.
        [
            test_quadkey,
            [
                # fmt: off
            pg.search_body_generator(qk=test_quadkey, has_next_page=True),
            pg.search_body_generator(qk=test_quadkey, has_next_page=False),
            pg.search_body_generator(qk=test_quadkey, has_next_page=False),
            pg.search_body_generator(qk=test_quadkey, has_next_page=False),
            pg.search_body_generator(qk=test_quadkey, has_next_page=False),
                # fmt: on
            ],
            4,
        ],
    ),
)
@pytest.mark.django_db(transaction=True)
def test_task_register_listings_or_divide_at_quadkey(
    quadkey,
    mock_airbnb_client,
    response_queue,
    responses,
    celery_worker,
    celery_app,
    listings_model,
    ubdcgrid_model,
    expected_grids,
    ubdctask_model,
    responses_model,
):
    """Test the task for registering listings or dividing at quadkey.
    """
    from ubdc_airbnb.tasks import task_register_listings_or_divide_at_quadkey

    ubdcgrid_model.objects.create_from_quadkey(quadkey)

    # aoi = aoishape_model.objects.create(name="test", geom_3857=grid.geom_3857, collect_listing_details=True)

    for rq in responses:
        content = {
            "content": rq,
        }
        response_queue.put(content)

    task = task_register_listings_or_divide_at_quadkey.s(quadkey=quadkey)
    result = task.apply_async()

    rr = [x for x, _ in result.collect() if type(x).__name__ == "AsyncResult"]

    assert listings_model.objects.count() == 10 * len(responses)
    assert ubdcgrid_model.objects.filter(quadkey__startswith=quadkey).count() == expected_grids
    for idx, r in enumerate(rr):
        ubdc_t = ubdctask_model.objects.get(task_id=r.id)
        resp = responses_model.objects.get(ubdc_task_id=r.id)

        assert ubdc_t == resp.ubdc_task

        if ubdc_t.task_name.endswith("divide_at_quadkey"):
            assert ubdc_t.task_kwargs["quadkey"].startswith(quadkey)

        if ubdc_t.task_name.endswith("task_get_next_page_homes"):

            # check that the parent task is the previous task.
            assert ubdc_t.task_kwargs["parent_page_task_id"] == rr[idx - 1].id
