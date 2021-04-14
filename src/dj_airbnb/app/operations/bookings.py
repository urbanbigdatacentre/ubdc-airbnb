from typing import Union, List, Sequence

from celery import chain, group, shared_task
from celery.result import GroupResult, AsyncResult
from dateutil.relativedelta import relativedelta
from django.db.models import Subquery, Q, F
from django.utils import timezone

from app.models import AOIShape, UBDCGroupTask, AirBnBListing, UBDCTask
from app.tasks import task_update_calendar, task_get_booking_detail


@shared_task
def op_get_booking_detail_for_listing_id(listing_id: Union[str, int]) -> AsyncResult:
    """
    Get booking_details for a number of listings_ids. Cost is 2 API calls per action.
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
def op_get_booking_detail_periodical(how_many:int = 500, age_hours: int = 23, priority: int = 5,
                                     use_aoi=True):
    how_many = int(how_many)
    age_hours = int(age_hours)
    expire_23hour_later = 23 * 60 * 60

    start_day_today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if use_aoi:
        qs_aoi = AOIShape.objects.filter(collect_bookings=True)
        target_listings = AirBnBListing.objects.filter(geom_3857__intersects=Subquery(qs_aoi.values('geom_3857')))
    else:
        target_listings = AirBnBListing.objects.all()

    # scheduled_listing_ids = UBDCTask.objects

    target_listings = (target_listings.filter(
        Q(calendar_updated_at__lt=start_day_today - relativedelta(hours=age_hours)) |
        Q(calendar_updated_at__isnull=True))
                       # .exclude(listing_id__in=Subquery(submitted_listing_ids.values_list('listing_ids', flat=True)))
                       .order_by(F('calendar_updated_at').asc(nulls_first=True)))
    target_listings = target_listings[:how_many]

    if target_listings.exists():
        listing_ids = list(target_listings.values_list('listing_id', flat=True))

        job = group(op_get_booking_detail_for_listing_id.s(listing_id=listing_id) for listing_id in listing_ids)
        group_result: GroupResult = job.apply_async(priority=priority, expires=expire_23hour_later)

        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
        group_task.op_name = task_update_calendar.name
        group_task.op_initiator = op_get_booking_detail_periodical.name
        group_task.op_kwargs = {'listing_ids': listing_ids}
        group_task.save()

        return group_result.id


__all__ = [
    'op_get_booking_detail_for_listing_id',
    'op_get_booking_detail_periodical'
]
