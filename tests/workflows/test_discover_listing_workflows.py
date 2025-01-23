import pytest
from mercantile import quadkey_to_tile, bounds, LngLatBbox
from collections import namedtuple
from faker import Faker

fake = Faker()
static_uuid4 = fake.uuid4(cast_to=str)


# https://labs.mapbox.com/what-the-tile/
test_quadkey = "0311332233311"  # glasgow city centre
methil_quadkey = "031133231323"  # methil, fife.
a_long_qk = "031133231323031133231323"  # 24 characters long

TASK_TIMEOUT = 10 * 60  # 10 minutes


def search_body_gen(
        qk: str,
        has_next_page: bool = False,
        federated_search_session_id: str = static_uuid4,
        number_of_listings=10) -> dict:

    tile = quadkey_to_tile(qk)
    rv = {}
    bbox: LngLatBbox = bounds(tile)
    lng = (bbox.east + bbox.west) / 2
    lat = (bbox.north + bbox.south) / 2

    random_ids = [fake.random_int(min=10000, max=10000000) for _ in range(number_of_listings)]
    explore_tabs = [
        {
            "tab_id": "home_tab",
            "pagination_metadata": {
                "has_next_page": has_next_page,
                "items_offset": 28,
                "previous_page_items_offset": 0,
            },
            "sections": [
                {},
                {},
                {
                    "listings": [
                        {
                            "listing": {
                                "city": fake.city(),
                                "id": id,
                                "id_str": str(id),
                                "lat": float(fake.coordinate(lat, 0.0001)),
                                "lng": float(fake.coordinate(lng, 0.0001)),
                                "user": {
                                    "first_name": fake.first_name(),
                                    "id": fake.random_int(),
                                }
                            }}
                        for id in random_ids
                    ],
                },
            ],
            "home_tab_metadata": {
                "listings_count": number_of_listings,
                "geography": {
                    "ne_lat": bbox.north,
                    "ne_lng": bbox.east,
                    "sw_lat": bbox.south,
                    "sw_lng": bbox.west,
                }
            }
        },
    ]
    metadata = {
        "federated_search_session_id": federated_search_session_id,
        "geography": {
            "ne_lat": bbox.north,
            "ne_lng": bbox.east,
            "sw_lat": bbox.south,
            "sw_lng": bbox.west,
        }
    }
    layout = {}
    filters = {}
    page_title = {}
    search_header = {}
    search_footer = {}

    rv.update(
        explore_tabs=explore_tabs,
        metadata=metadata,
        layout=layout,
        filters=filters,
        page_title=page_title,
        search_header=search_header,
        search_footer=search_footer,
    )

    return rv


response_data = namedtuple(
    typename="response_data",
    field_names=["status_code", "body", "headers",],
    defaults=[200, search_body_gen("0311332233311"), {}],


)


@pytest.mark.parametrize(
    "quadkey,responses,expected_grids",
    (
        # emulate a normal quadkey, which has 1 page of results.
        [methil_quadkey, [response_data(body=search_body_gen(methil_quadkey))], 1],
        # emulate a long quadkey, which has 3 pages of results.
        [a_long_qk, [
            # fmt: off
            response_data(body=search_body_gen(a_long_qk, has_next_page=True)),
            response_data(body=search_body_gen(a_long_qk, has_next_page=True)),
            response_data(body=search_body_gen(a_long_qk, has_next_page=False)),
            # fmt: on
        ], 1],
        [test_quadkey, [
            # fmt: off
            response_data(body=search_body_gen(test_quadkey, has_next_page=True)),
            response_data(body=search_body_gen(test_quadkey, has_next_page=False)),
            response_data(body=search_body_gen(test_quadkey, has_next_page=False)),
            response_data(body=search_body_gen(test_quadkey, has_next_page=False)),
            response_data(body=search_body_gen(test_quadkey, has_next_page=False)),
            # fmt: on
        ], 4],
    ),
)
@ pytest.mark.django_db(transaction=True)
def test_get_listings_at_grid(
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
    from ubdc_airbnb.tasks import task_register_listings_or_divide_at_quadkey
    ubdcgrid_model.objects.create_from_quadkey(quadkey)

    # aoi = aoishape_model.objects.create(name="test", geom_3857=grid.geom_3857, collect_listing_details=True)

    for rq in responses:
        response_data = {}
        response_data.update(
            status_code=rq.status_code,
            body=rq.body,
            headers=rq.headers,
        )
        response_queue.put(response_data)

    task = task_register_listings_or_divide_at_quadkey.s(quadkey=quadkey)
    result = task.apply_async()

    rr = [x for x, _ in result.collect() if type(x).__name__ == 'AsyncResult']

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
            assert ubdc_t.task_kwargs["parent_page_task_id"] == rr[idx-1].id
