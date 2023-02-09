from typing import List, Optional, Sequence, Union, TYPE_CHECKING

from celery import group, shared_task
from celery.result import GroupResult
from celery.utils.log import get_task_logger
from django.db.models import F, Q
from django.utils.timezone import now

from ubdc_airbnb.errors import UBDCError
from ubdc_airbnb.models import AOIShape, UBDCGroupTask, AirBnBListing
from ubdc_airbnb.tasks import task_update_calendar
from ubdc_airbnb.utils.spatial import get_listings_qs_for_aoi
from ubdc_airbnb.utils.tasks import get_engaged_listing_ids_for

logger = get_task_logger(__name__)

if TYPE_CHECKING:
    from django.db.models import QuerySet


@shared_task
def op_update_calendars_for_listing_ids(
    listing_id: Union[int, Sequence[int]],
) -> str:
    """TODO: DOC"""

    if isinstance(listing_id, Sequence):
        _listing_ids = listing_id
    else:
        _listing_ids = (listing_id,)

    job = group(task_update_calendar.s(listing_id=listing_id) for listing_id in _listing_ids)

    group_result: GroupResult = job.apply_async()
    group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
    group_task.op_name = task_update_calendar.name
    group_task.op_kwargs = {"listing_id": _listing_ids}
    group_task.save()

    return group_result.id


@shared_task
def op_update_calendar_at_aoi(id_shape: Union[int, Sequence[int]]) -> Optional[str]:
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

        group_result: GroupResult = job.apply_async()
        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
        group_task.op_initiator = op_update_calendar_at_aoi.name
        group_task.op_name = task_update_calendar.name
        group_task.op_kwargs = {"listing_id": listing_ids}
        group_task.save()

        return group_result.id


# with 75 active workers we have a capacity of ~17k request/hour. The task will run every 4 hours.
@shared_task
def op_update_calendar_periodical(
    how_many: int = 17_000 * 2.5,
    priority: int = 5,
    use_aoi: bool = True,
) -> Optional[str]:
    how_many = int(how_many)
    priority = int(priority)

    if how_many < 0:
        raise UBDCError("The variable how_many must be larger than 0")
    if not (0 < priority <= 10):
        raise UBDCError("The variable priority must be between 1 and 10")

    logger.info(f"Using AOI: {use_aoi}")
    if use_aoi:
        qs_listings = get_listings_qs_for_aoi("calendar")
    else:
        qs_listings: "QuerySet" = AirBnBListing.objects.all()

    logger.info(f"Listings that eligible to process: \t{qs_listings.count()}")

    # select only the listings who have not been queried 8 o'clock today or are null
    timestamp_threshold = now().replace(hour=8, minute=0, second=0, microsecond=0)
    qs_listings.filter(Q(calendar_updated_at__lte=timestamp_threshold) | Q(calendar_updated_at__isnull=True))
    logger.info(f"Listings that have not been  processed today: \t{qs_listings.count()}")

    # Find the listing that have not been acted in the last 24 hours
    engaged_listings = get_engaged_listing_ids_for(purpose="calendars")
    logger.info(f"Listings that have been submitted by previous run: \t{engaged_listings.count()}")
    qs_listing_ids = qs_listings.exclude(listing_id__in=engaged_listings)
    logger.info(f"Listings after excluding these:  {qs_listing_ids.count()}")

    qs_listings = (
        AirBnBListing.objects.filter(listing_id__in=qs_listing_ids).order_by(
            F("calendar_updated_at").asc(nulls_first=True)
        )
    )[:how_many]

    logger.info(f"NUmber of listings that will act (limited on the upper limit): \t{qs_listings.count()}")
    if qs_listings.exists():
        listing_ids = list(qs_listings.values_list("listing_id", flat=True))
        job = group(task_update_calendar.s(listing_id=listing_id) for listing_id in listing_ids)
        group_result: GroupResult = job.apply_async(priority=priority)

        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
        group_task.op_name = task_update_calendar.name
        group_task.op_initiator = op_update_calendar_periodical.name
        group_task.op_kwargs = {"listing_id": listing_ids}
        group_task.save()

        return group_result.id
    logger.info(f"No listings for listing_details have been found!")
    return None


__all__ = [
    "op_update_calendars_for_listing_ids",
    "op_update_calendar_at_aoi",
    "op_update_calendar_periodical",
]
