from datetime import timedelta
from typing import TYPE_CHECKING, List, Optional, Sequence, Union

from celery import group, shared_task
from celery.result import AsyncResult, GroupResult
from celery.utils.log import get_task_logger
from django.db.models import F, Q
from django.utils.timezone import now

from ubdc_airbnb.errors import UBDCError
from ubdc_airbnb.models import AirBnBListing, AOIShape, UBDCGroupTask
from ubdc_airbnb.tasks import task_update_calendar
from ubdc_airbnb.utils.spatial import get_listings_qs_for_aoi
from ubdc_airbnb.utils.tasks import get_submitted_listing_ids_for
from ubdc_airbnb.utils.time import end_of_day, seconds_from_now

logger = get_task_logger(__name__)

if TYPE_CHECKING:
    from django.db.models import QuerySet


@shared_task
def op_update_calendars_for_listing_ids(
    listing_id: Union[int, Sequence[int]],
) -> str:
    """Returns the group id"""

    end_of_today = end_of_day()

    if isinstance(listing_id, Sequence):
        _listing_ids = listing_id
    else:
        _listing_ids = (listing_id,)

    job = group(task_update_calendar.s(listing_id=listing_id).set(expires=end_of_today) for listing_id in _listing_ids)

    group_result: AsyncResult[GroupResult] = job.apply_async()
    group_result.save()  # type: ignore # typing issue?
    group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
    group_task.op_name = task_update_calendar.name
    group_task.op_kwargs = {"listing_id": _listing_ids}
    group_task.save()

    return group_result.id


@shared_task
def op_update_calendar_at_aoi(
    id_shape: Union[int, Sequence[int]],
) -> str | None:
    """Fetch and add the calendars for the listings_ids in these AOIs to the database.
    :param id_shape: pk of ::AOIShape::
    :type id_shape: int or List[int]

    :returns
    """

    if isinstance(id_shape, Sequence):
        id_shapes = id_shape
    else:
        id_shapes = (id_shape,)

    qs_listings = AirBnBListing.objects.none()
    for aoi_id in id_shapes:
        aoishape = AOIShape.objects.get(id=aoi_id)
        qs_listings |= aoishape.listings

    if qs_listings.exists():
        listing_ids = qs_listings.values_list("listing_id", flat=True)
        job = group(task_update_calendar.s(listing_id=listing_id) for listing_id in listing_ids)

        group_result: AsyncResult[GroupResult] = job.apply_async()
        group_result.save()  # type: ignore # typing issue?
        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
        group_task.op_initiator = op_update_calendar_at_aoi.name
        group_task.op_name = task_update_calendar.name
        group_task.op_kwargs = {"listing_id": listing_ids}
        group_task.save()

        return group_result.id


# 75 active workers consume about ~17k request/hour.
# this is the main beat task. It will run once per day at 2 am.
# configure it at ubdc_airbnb.core.celery
@shared_task(acks_late=False)
def op_update_calendar_periodical(use_aoi=True, **kwargs) -> list[str]:
    """
    It will generate tasks to collect all listing calendars all the activated AOIs by default.

    Tasks are marked to expire 10 mins before the end of today.
    """
    end_of_today = end_of_day()
    group_result_ids: list[str] = []

    logger.info(f"Using AOI: {use_aoi}")
    if use_aoi:
        qs_listings = get_listings_qs_for_aoi("calendar")
    else:
        qs_listings: "QuerySet" = AirBnBListing.objects.all()

    # process them by 10000;
    if qs_listings.exists():
        _listing_ids = []
        for idx, listing in enumerate(qs_listings.iterator(chunk_size=10000)):
            _listing_ids.append(listing.listing_id)
            if idx % 10000 == 0 and idx > 0:
                logger.info(f"Submiting job for {idx} listings")
                job = group(
                    task_update_calendar.s(listing_id=listing_id).set(expires=end_of_today)
                    for listing_id in _listing_ids
                )
                group_result: AsyncResult[GroupResult] = job.apply_async()
                group_result_id = group_result.id
                group_result.save()  # type: ignore # typing issue?
                group_task = UBDCGroupTask.objects.get(group_task_id=group_result_id)
                group_task.op_name = task_update_calendar.name
                group_task.op_initiator = op_update_calendar_periodical.name
                group_task.op_kwargs = {"listing_id": _listing_ids}
                group_task.save()
                logger.info(f"Submited as job {group_result_id}")
                group_result_ids.append(group_result_id)
                _listing_ids.clear()

    return group_result_ids


__all__ = [
    "op_update_calendars_for_listing_ids",
    "op_update_calendar_at_aoi",
    "op_update_calendar_periodical",
]
