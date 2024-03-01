from typing import Union

from celery import chain, group, shared_task
from celery.result import AsyncResult, GroupResult
from celery.utils.log import get_task_logger
from dateutil.relativedelta import relativedelta
from django.db.models import Count, F, OuterRef, Q, Subquery
from django.utils import timezone

from ubdc_airbnb.models import AirBnBListing, AOIShape, UBDCGroupTask
from ubdc_airbnb.tasks import task_get_booking_detail, task_update_calendar
from ubdc_airbnb.utils.time import seconds_from_now

logger = get_task_logger(__name__)


@shared_task
def op_get_booking_detail_for_listing_id(
    listing_id: Union[str, int],
) -> str:
    """
    Get booking_details for a  listings_id. Costs is 2 API calls per action.
    Task will harvest a new calendar
    """
    listing_id = int(listing_id)

    task = chain(task_update_calendar.s(listing_id=listing_id), task_get_booking_detail.s())
    result: AsyncResult = task()  # calling a chain applies apply_async

    # group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
    #
    # group_task.op_name = '+'.join((task_update_calendar.name, task_get_booking_detail.name))
    # group_task.op_initiator = op_get_booking_detail_for_listing_ids.name
    # group_task.op_kwargs = {'listing_id': listing_id}
    # group_task.save()

    return result.id


@shared_task
def op_get_booking_detail_periodical(
    how_many: int = 500,
    age_hours: int = 23,
    priority: int = 5,
    use_aoi=True,
):
    how_many = int(how_many)
    age_hours = int(age_hours)

    expire_23hour_later = seconds_from_now()

    start_day_today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if use_aoi:
        qs_aoi = AOIShape.objects.filter(collect_bookings=True, geom_3857__intersects=OuterRef("geom_3857"))[:1]
        qs_listings = AirBnBListing.objects.annotate(x=Count(Subquery(qs_aoi.values("id")))).filter(x__gte=1)
        logger.info(f"Found {qs_listings.count()} listings")
    else:
        qs_listings = AirBnBListing.objects.all()

    # scheduled_listing_ids = UBDCTask.objects

    qs_listings = (
        qs_listings.filter(
            Q(calendar_updated_at__lt=start_day_today - relativedelta(hours=age_hours))
            | Q(calendar_updated_at__isnull=True)
        )
        # .exclude(listing_id__in=Subquery(submitted_listing_ids.values_list('listing_ids', flat=True)))
        .order_by(F("calendar_updated_at").asc(nulls_first=True))
    )
    qs_listings = qs_listings[:how_many]

    if qs_listings.exists():
        listing_ids = list(qs_listings.values_list("listing_id", flat=True))

        job = group(op_get_booking_detail_for_listing_id.s(listing_id=listing_id) for listing_id in listing_ids)
        group_result: AsyncResult[GroupResult] = job.apply_async(
            priority=priority,
            expires=expire_23hour_later,
        )
        group_result.save()  # type: ignore # typing issue?

        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
        group_task.op_name = task_update_calendar.name
        group_task.op_initiator = op_get_booking_detail_periodical.name
        group_task.op_kwargs = {"listing_ids": listing_ids}
        group_task.save()

        return group_result.id


__all__ = [
    "op_get_booking_detail_for_listing_id",
    "op_get_booking_detail_periodical",
]
