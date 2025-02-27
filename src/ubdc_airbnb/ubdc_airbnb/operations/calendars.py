from typing import TYPE_CHECKING, Sequence, Union

from celery import group, shared_task
from celery.result import AsyncResult, GroupResult
from celery.utils.log import get_task_logger
from django.conf import settings
from django.db.models import Q

from ubdc_airbnb.models import AirBnBListing, AOIShape, UBDCGroupTask
from ubdc_airbnb.tasks import task_update_calendar
from ubdc_airbnb.utils.time import end_of_day, start_of_day


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

    job = group(task_update_calendar.s(listing_id=listing_id).set(expires=end_of_today)
                for listing_id in _listing_ids)

    group_result: AsyncResult[GroupResult] = job.apply_async()
    group_result.save()  # type: ignore
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
def op_update_calendar_periodical(use_aoi=True, **kwargs) -> None:
    """
    It will generate tasks to collect all listing calendars all the activated AOIs by default.
    Tasks are marked to expire at the end of today.
    """
    start_of_today = start_of_day()
    end_of_today = end_of_day()

    group_result_ids: list[str] = []

    logger.info(f"Filter AOIs on collect_calendars? {use_aoi}")
    if use_aoi:
        qs_listings = AirBnBListing.objects.for_purpose("calendar")
    else:
        qs_listings = AirBnBListing.objects.all()

    if kwargs.get("stale", False):
        # assume that something had happened and interuppted the service;
        # if we re-run we  we want to update only the calendars that were not updated today (yet)
        logger.info("Filtering for stale calendars")
        q = (Q(calendar_updated_at__lt=start_of_today) | Q(calendar_updated_at=None))
        qs_listings = qs_listings.filter(q)

    def process_group(batch: list[int]) -> None:
        logger.info(f"Submiting job for {idx} listings")
        job = group(task_update_calendar.s(listing_id=listing_id).set(expires=end_of_today)
                    for listing_id in batch)
        group_result: AsyncResult[GroupResult] = job.apply_async()
        group_result.save()  # type: ignore
        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
        group_task.op_name = task_update_calendar.name
        group_task.op_initiator = op_update_calendar_periodical.name
        group_task.op_kwargs = {"listing_id": batch}
        group_task.save()

    chunk_size = settings.CELERY_TASK_CHUNK_SIZE
    if qs_listings.exists():
        total_listings = qs_listings.count()
        logger.info(f"Processing {total_listings} listings")
        listing_ids = qs_listings.values_list("listing_id", flat=True)
        batch = []
        for idx, listing in enumerate(listing_ids.iterator(chunk_size=chunk_size*2)):
            batch.append(listing)
            if idx % chunk_size == 0 and idx > 0:
                process_group(batch)
                batch.clear()

        # process the last batch
        process_group(batch)

    return


__all__ = [
    "op_update_calendars_for_listing_ids",
    "op_update_calendar_at_aoi",
    "op_update_calendar_periodical",
]
