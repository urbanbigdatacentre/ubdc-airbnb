from typing import List, Optional, Sequence, Union

from celery import group, shared_task
from celery.result import GroupResult
from dateutil.relativedelta import relativedelta
from django.contrib.postgres.fields.jsonb import KeyTextTransform
from django.db.models import F, IntegerField, Q, QuerySet, Subquery, OuterRef
from django.db.models.functions import Cast
from django.utils.timezone import now
from celery.utils.log import get_task_logger
from app.errors import UBDCError
from app.models import AOIShape, AirBnBListing, UBDCGroupTask, UBDCTask
from app.tasks import task_update_or_add_reviews_at_listing

logger = get_task_logger(__name__)


@shared_task
def op_update_comment_at_listings(listing_id: Union[int, Sequence[int]], force_check=False) -> GroupResult:
    """  Submit jobs for fetching the reviews from listing_ids
    """

    if isinstance(listing_id, Sequence):
        listing_ids = listing_id
    else:
        listing_ids = (listing_id,)

    tasks_list = []
    for idx in listing_ids:
        task = task_update_or_add_reviews_at_listing.s(listing_id=idx, force_check=force_check)
        tasks_list.append(task)

    job = group(tasks_list)
    group_result: GroupResult = job.apply_async()
    group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)

    group_task.op_name = task_update_or_add_reviews_at_listing.name
    group_task.op_initiator = op_update_comment_at_listings.name
    group_task.op_kwargs = {'listing_id': listing_ids}
    group_task.save()

    return group_result


@shared_task
def op_update_reviews_aoi(id_shape: Union[int, Sequence[int]], force_check=False) -> List[str]:
    """
    :param id_shape: single or sequence of ints representing pks of id_shapes
    :param force_check: check all comment history, defaults to False
    :type force_check: bool
    """

    if isinstance(id_shape, Sequence):
        id_shapes = id_shape
    else:
        id_shapes = (id_shape,)

    job_list = []
    for _id_shape in id_shapes:
        aoi_shape = AOIShape.objects.get(id=_id_shape)
        listings = aoi_shape.listings

        listing_ids = [x.listing_id for x in listings]
        kwargs = {'listing_id': listing_ids, 'force_check': force_check}
        task = op_update_comment_at_listings.s(**kwargs)
        job_list.append(task)

    group_job = group(job_list)
    group_result = group_job.apply_async()

    group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
    group_task.op_name = op_update_comment_at_listings.name
    group_task.op_initiator = op_update_reviews_aoi.name
    group_task.op_kwargs = {'id_shape': id_shape, 'force_check': force_check}
    group_task.save()

    return group_result.id


# CELERY BEAT
# There are ~250k listings in UK. Could burn through bandwidth really fast, as it will fetch user details as well
@shared_task
def op_update_reviews_periodical(how_many: int = 50, age_hours: int = 3 * 7 * 24, priority: int = 4,
                                 use_aoi: bool = True) -> Optional[str]:
    """
    An 'initiator' task that will select at the most 'how_many' (default 50) listings had not had their reviews
    harvested for more than 'age_days' (default 21) days.
        For each of these listing a task will be created with priority 'priority' (default 4).
        These tasks will take care of adding any new users into the database.
        The tasks are hard-coded to expire, if not completed, in 23 hours after they been published.

    Return is a task_group_id UUID string that  these tasks will operate under.
    In case there are no listings found None will be returned instead

    :param use_aoi: If true, the listings will be selected only from the aoi_shapes that have been designated to this task, default  true
    :param how_many:  Maximum number of listings to act, defaults to 5000
    :param age_hours: How many HOURS before from the last update, before the it will be considered stale. int > 0, defaults two weeks
    :param priority:  priority of the tasks generated. int from 1 to 10, 10 being maximum. defaults to 4
    :return: str(UUID)
    """

    if how_many < 0:
        raise UBDCError('The variable how_many must be larger than 0')
    if age_hours < 0:
        raise UBDCError('The variable age_days must be larger than 0')
    if not (0 < priority < 10 + 1):
        raise UBDCError('The variable priority must be between 1 than 10')

    expire_23hour_later = 23 * 60 * 60

    if use_aoi:
        qs_aoi = AOIShape.objects.filter(collect_reviews=True, geom_3857__intersects=OuterRef('geom_3857'))[:1]
        qs_listings = AirBnBListing.objects.filter(
            geom_3857__intersects=Subquery(qs_aoi.values('geom_3857')))
        logger.info(f"Found {qs_listings.count()} listings")
    else:
        qs_listings = AirBnBListing.objects.all()

    start_day_today = now().replace(hour=0, minute=0, second=0, microsecond=0)
    submitted_listing_ids = (UBDCTask.objects
                             .filter(datetime_submitted__gte=start_day_today - relativedelta(days=1))
                             .filter(task_name=task_update_or_add_reviews_at_listing.name)
                             .filter(status=UBDCTask.TaskTypeChoices.SUBMITTED)
                             .filter(task_kwargs__has_key='listing_id')
                             .annotate(listing_ids=Cast(KeyTextTransform('listing_id', 'task_kwargs'), IntegerField())))

    qs_listings = (qs_listings.filter(
        Q(reviews_updated_at__lt=start_day_today - relativedelta(hours=age_hours)) |
        Q(reviews_updated_at__isnull=True))
                   .exclude(listing_id__in=Subquery(submitted_listing_ids.values_list('listing_ids', flat=True)))
                   .order_by(F('calendar_updated_at').asc(nulls_first=True)))

    if qs_listings.exists():
        listing_ids = list(qs_listings.values_list('listing_id', flat=True)[0:how_many])
        job = group(task_update_or_add_reviews_at_listing.s(listing_id=listing_id) for listing_id in listing_ids)
        group_result: GroupResult = job.apply_async(priority=priority, expires=expire_23hour_later)

        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
        group_task.op_name = task_update_or_add_reviews_at_listing.name
        group_task.op_initiator = op_update_reviews_periodical.name
        group_task.op_kwargs = {'listing_id': listing_ids}
        group_task.save()

        return group_result.id
    return None
