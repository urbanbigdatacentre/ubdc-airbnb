from typing import TYPE_CHECKING
from collections import namedtuple
import pytest
from celery.result import GroupResult

response_data = namedtuple(
    typename="response_data",
    field_names=["status_code", "body", "headers",],
    defaults=[200, {}, {}]
)


@pytest.mark.parametrize(
    "listing_id,responses",
    [
        # listing_id, responses
        (900,            [response_data()]),
        (1316740343258461084, [response_data()]),  # a very large (real) listing_id
        (900.0,           [response_data()]),  # listing_id as float.
        (900,            [response_data(403)]),  # Forbidden
        (900,            [  # first response is 429,then retry, then 200
            response_data(429, {}, {}),  # Too many requests
            response_data(200, {}, {}),  # then ok
        ]),
        (900,            [  # first response is 429,then retry, then 200
            response_data(429, {}, {}),  # Too many requests x 3 times;  fail
            response_data(429, {}, {}),
            response_data(429, {}, {}),
        ]),
        (900,            [
            response_data(503, headers={"X-Crawlera-Error": "banned"})],
         ),
    ],
)
@pytest.mark.django_db(transaction=True)
def test_op_update_calendars_for_listing_ids(
    mock_airbnb_client,
    response_queue,
    responses: list[response_data],
    listings_model,
    celery_worker,
    celery_app,
    listing_id,
):
    """Given a listing, run the workflow to get their calendars."""

    from ubdc_airbnb.operations import op_update_calendars_for_listing_ids

    for rq in responses:
        response_data = {}
        response_data.update(
            listing_id=listing_id,
            status_code=rq.status_code,
            headers=rq.headers,
        )
        response_queue.put(response_data)

    task = op_update_calendars_for_listing_ids.s([listing_id])
    # fire the task
    result = task.apply_async()

    # get the group result id
    group_result_id = result.get()

    group_result = GroupResult.restore(group_result_id)  # type: ignore
    assert group_result is not None
    assert group_result.children is not None
    # assert job.children is populated

    # join_native does not support django db backend
    g = group_result.join(propagate=False)

    from ubdc_airbnb.models import AirBnBResponse

    # regarlless of the number of responses, the last one is the one that counts
    expected_status_code = [r.status_code for r in responses][-1]

    rf = AirBnBResponse.objects.filter(listing_id=listing_id)
    assert rf.count() == 1
    r: AirBnBResponse = rf.first()  # type: ignore
    assert r.status_code == expected_status_code
    from uuid import UUID
    assert r.ubdc_task.group_task_id == UUID(group_result_id)  # type: ignore
    assert r._type == 'CAL'
