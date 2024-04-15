from typing import TYPE_CHECKING

import pytest
from celery.result import GroupResult


@pytest.mark.parametrize(
    "listing_ids",
    [
        (900, 9001),
        (800, 80000000000001),
    ],
)
@pytest.mark.django_db(transaction=True)
def test_op_update_calendars_for_listing_ids(
    mock_airbnb_client,
    listings_model,
    celery_worker,
    celery_app,
    listing_ids,
):
    """Given a set of listing, run the workflow to get their calendars."""

    from ubdc_airbnb.models import AirBnBResponse
    from ubdc_airbnb.operations import op_update_calendars_for_listing_ids

    task = op_update_calendars_for_listing_ids.s([x for x in listing_ids])
    # fire the task
    result = task.apply_async()

    # get the group result id
    group_result_id = result.get()

    group_result = GroupResult.restore(group_result_id)  # type: ignore
    assert group_result is not None
    assert group_result.children is not None
    ## assert job.children is populated

    ## join_native does not support django db backend
    g = group_result.join(propagate=False)

    r = AirBnBResponse.objects.filter(listing_id__in=listing_ids)
    assert r.count() == 2
    assert r.filter(status_code=200).count() == 2
    assert r.filter(_type="CAL").count() == 2
    assert r.filter(ubdc_task__status="SUCCESS").count() == 2
    for ar in r:
        ubdc_task = ar.ubdc_task
        assert ubdc_task is not None  #
        listing_id_str = str(ar.listing_id)
        if listing_id_str == "800":
            assert ubdc_task.retries == 2
        else:
            assert ubdc_task.retries == 0


# def test_get_calendar_for_listing_id_w_retry(
#     mock_airbnb_client,
#     listings_model,
#     celery_worker,
#     celery_app,
# ):
#     task = op_update_calendars_for_listing_ids.s([x for x in listing_ids])


#         print('do some actual testing')

#     def test_get_calendar_404(self):
#         from ubdc_airbnb.tasks import task_update_calendar

#         task = task_update_calendar.s(listing_id=self.listing_404)
#         job = task.apply_async()

#         ref = None
#         with self.assertRaises(UBDCError) as exc:
#             job.get()
#             ref = exc

#         print('end')

#     def test_scan_for_listings(self):
#         from ubdc_airbnb.operations import op_discover_new_listings_at_grid

#         task = op_discover_new_listings_at_grid.s(self.quadkey)
#         job = task.apply_async()
#         time.sleep(1)
#         while not all(list(x.ready() for x in job.children)):
#             print('waiting...')
#             time.sleep(1)
#         group_result_id = job.get()

#         print('do some actual testing')

#     def test_grab_listing_calendar_non_existent(self):
#         from ubdc_airbnb.operations import op_update_calendars_for_listing_ids
#         from ubdc_airbnb.models import AirBnBResponse
#         from ubdc_airbnb.errors import UBDCRetriableError

#         from ubdc_airbnb.errors import UBDCError

#         task = op_update_calendars_for_listing_ids.s(self.listing_404)

#         job = task.apply_async()
#         time.sleep(1)
#         while not all(list(x.ready() for x in job.children)):
#             print('waiting...')
#             time.sleep(1)

#         try:
#             list(job.collect())
#         except (UBDCRetriableError, UBDCError) as exc:
#             r = AirBnBResponse.objects.filter(listing_id=self.listing_404).first()
#             self.assertIsNotNone(r)
#             self.assertIn(r.status_code, [503, 403], 'unexpected return code')
#             self.assertEqual(r._type, AirBnBResponseTypes.calendar)
#         else:
#             self.fail('error was not raised')
