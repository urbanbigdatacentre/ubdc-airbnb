from typing import List, Optional, Sequence, Union

from celery import group, shared_task
from celery.result import GroupResult
from celery.utils.log import get_task_logger
from dateutil.relativedelta import relativedelta
from django.contrib.postgres.fields.jsonb import KeyTextTransform
from django.db.models import F, IntegerField, Q, QuerySet, Subquery
from django.db.models.functions import Cast
from django.utils.timezone import now

from app.models import AOIShape, UBDCGroupTask, AirBnBListing, UBDCTask
from app.tasks import task_update_calendar

logger = get_task_logger(__name__)

_23hour_later = 23 * 60 * 60


@shared_task
def op_update_calendars_for_listing_ids(listing_id: Union[int, Sequence[int]], ) -> str:
    """ TODO: DOC """

    if isinstance(listing_id, Sequence):
        _listing_ids = listing_id
    else:
        _listing_ids = (listing_id,)

    job = group(task_update_calendar.s(listing_id=listing_id) for listing_id in _listing_ids)

    group_result: GroupResult = job.apply_async()
    group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
    group_task.op_name = task_update_calendar.name
    group_task.op_kwargs = {'listing_id': _listing_ids}
    group_task.save()

    return group_result.id


@shared_task
def op_update_calendar_at_aoi(id_shape: Union[int, Sequence[int]]) -> Optional[str]:
    """ Fetch and add the calendars for the listings_ids in these AOIs to the database.
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
        listing_ids = qs_listings.values_list('listing_id', flat=True)
        job = group(task_update_calendar.s(listing_id=listing_id) for listing_id in listing_ids)

        group_result: GroupResult = job.apply_async()
        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
        group_task.op_initiator = op_update_calendar_at_aoi.name
        group_task.op_name = task_update_calendar.name
        group_task.op_kwargs = {'listing_id': listing_ids}
        group_task.save()

        return group_result.id


# with 75 active workers we have a capacity of ~17k request/hour. The task will run every 4 hours.
@shared_task
def op_update_calendar_periodical(how_many: int = 17_000 * 2.5, age_hours: int = 23, priority: int = 5,
                                  use_aoi_shapes=True) -> Optional[str]:
    how_many = int(how_many)
    qs_listings: QuerySet = AirBnBListing.objects.none()
    if use_aoi_shapes:
        enabled_aoi = AOIShape.objects.filter(collect_calendars=True)
        qs_listings = AirBnBListing.objects.filter(
            geom_3857__intersects=Subquery(enabled_aoi.values('geom_3857')))
        logger.info(f"Found {qs_listings.count()} listings")
    else:
        qs_listings = qs_listings.all()

    excluded_listings = (UBDCTask.objects
                         .filter(datetime_submitted__gte=now() - relativedelta(days=1))
                         .filter(task_name=task_update_calendar.name)
                         .filter(status=UBDCTask.TaskTypeChoices.SUBMITTED)
                         .filter(task_kwargs__has_key='listing_id')
                         .annotate(listing_id=Cast(KeyTextTransform('listing_id', 'task_kwargs'), IntegerField())))

    qs_listings = (qs_listings.filter(
        Q(calendar_updated_at__lt=now() - relativedelta(hours=age_hours)) |
        Q(calendar_updated_at__isnull=True))
        .exclude(listing_id__in=Subquery(excluded_listings.values_list('listing_id', flat=True))).order_by(
        F('calendar_updated_at').asc(nulls_first=True))
                  )[:how_many]
    logger.info(f"After final sorting found {qs_listings.count()} listings")
    if qs_listings.exists():
        listing_ids = list(qs_listings.values_list('listing_id', flat=True))
        job = group(task_update_calendar.s(listing_id=listing_id) for listing_id in listing_ids)
        group_result: GroupResult = job.apply_async(priority=priority, expires=_23hour_later)

        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
        group_task.op_name = task_update_calendar.name
        group_task.op_initiator = op_update_calendar_periodical.name
        group_task.op_kwargs = {'listing_id': listing_ids}
        group_task.save()

        return group_result.id


__all__ = ['op_update_calendars_for_listing_ids', 'op_update_calendar_at_aoi', 'op_update_calendar_periodical']
