from typing import List, Sequence, Union, Optional

from celery import group, shared_task
# Discover
from celery.result import GroupResult, AsyncResult
from celery.utils.log import get_task_logger
from dateutil.relativedelta import relativedelta
from django.contrib.postgres.fields.jsonb import KeyTextTransform
from django.db.models import TextField, Q, Subquery
from django.db.models.functions import Cast
from django.utils.timezone import now

from app.errors import UBDCError
from app.models import UBDCGroupTask, UBDCTask, UBDCGrid, AOIShape
from app.tasks import task_discover_listings_at_grid

logger = get_task_logger(__name__)


@shared_task
def op_discover_new_listings_at_grid(quadkey: Union[str, List[str]]) -> str:
    """ Add the calendars for the listings_id that are in this AOI to the database

    :param quadkey: Quadkey or quadkeys to search
    :returns: ..."""

    if isinstance(quadkey, Sequence) and not isinstance(quadkey, str):
        _quadkeys = quadkey
    else:
        _quadkeys = [quadkey, ]

    job = group(task_discover_listings_at_grid.s(quadkey=_qk) for _qk in _quadkeys)
    group_result = job.apply_async()

    group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)

    group_task.op_name = op_discover_new_listings_at_grid.name
    group_task.op_kwargs = {'quadkey': _quadkeys}
    group_task.save()

    return group_result.id


@shared_task
def op_discover_new_listings_periodical(how_many: int = 500,
                                        age_hours: int = 7 * 24,
                                        use_aoi: bool = True,
                                        priority=4) -> Optional[str]:
    """
    An 'initiator' task that will select at the most 'how_many' grids (default 500) that overlap
    with enabled AOIs and where scanned  more than 'age_days' (default 7) age. If how_many = None, it will default to the number of grids

    For each of these grids a task will be created with priority 'priority' (default 4).
    Any task generated from here is  hard-coded to expire, if not completed, in 23 hours after it was  published.

    Return is a task_group_id UUID string that  these tasks will operate under.
    In case there are no listings found None will be returned instead

    :param how_many:  Maximum number of listings to act, defaults to 500
    :param use_aoi:   Only scan grids that are intersect with the the AOIs.
    :param age_hours: How many DAYS before from the last update, before the it will be considered stale. int > 0, defaults to 14 (two weeks)
    :param priority:  priority of the tasks generated. int from 1 to 10, 10 being maximum. defaults to 4
    :return: str(UUID)
    """

    how_many = how_many or UBDCGrid.objects.count()

    if how_many < 0:
        raise UBDCError('The variable how_many must be larger than 0')
    if age_hours < 0:
        raise UBDCError('The variable age_days must be larger than 0')
    if not (0 < priority < 10 + 1):
        raise UBDCError('The variable priority must be between 1 than 10')

    how_many = int(how_many)
    age_hours = int(age_hours)
    priority = int(priority)

    expire_23hour_later = 23 * 60 * 60
    start_day_today = now().replace(hour=0, minute=0, second=0, microsecond=0)
    future_qk = list(
        UBDCTask
            .objects
            .filter(
            datetime_submitted__gte=start_day_today - relativedelta(days=1))  # datetime_submitted has index on it
            .filter(task_name=task_discover_listings_at_grid.name)
            .filter(status=UBDCTask.TaskTypeChoices.SUBMITTED)
            .filter(task_kwargs__has_key='quadkey')
            .annotate(quadkey=Cast(KeyTextTransform('quadkey', 'task_kwargs'), TextField()))
            .values_list('quadkey', flat=True)
    )

    if use_aoi:
        _aois = AOIShape.objects.filter(scan_for_new_listings=True)
        q_quadkeys = UBDCGrid.objects.filter(geom_3857__intersects=Subquery(_aois.values('geom_3857')))
    else:
        q_quadkeys = AOIShape.objects.all()

    q_quadkeys = (q_quadkeys
                  .exclude(quadkey__in=future_qk)
                  .filter(
        Q(datetime_last_listings_scan__lt=start_day_today - relativedelta(days=age_hours)) |
        Q(datetime_last_listings_scan__isnull=True))
                  .order_by('datetime_last_estimated_listings_scan')
                  .values_list('quadkey', flat=True))[0:how_many]

    _quadkeys = list(q_quadkeys[0:how_many])

    if len(_quadkeys) > 0:
        job = group(task_discover_listings_at_grid.s(quadkey=quadkey, ) for quadkey in _quadkeys)
        group_result: GroupResult = job.apply_async(priority=priority, expires=expire_23hour_later)

        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
        group_task.op_name = op_discover_new_listings_periodical.name
        group_task.op_kwargs = {'quadkey': _quadkeys}
        group_task.save()

        return group_result.id
    return None


@shared_task
def op_discover_new_listings_at_aoi(id_shape: Union[int, List[int]]) -> str:
    """ Add the calendars for the listings_id that are in this AOI to the database
        :param id_shape: pk of ::AOIShape::
    """

    if isinstance(id_shape, Sequence):
        id_shapes = id_shape
    else:
        id_shapes = (id_shape,)

    quadkeys = set()
    for _id in id_shapes:
        aoi_shape = AOIShape.objects.get(id=_id)
        _quadkeys = UBDCGrid.objects.filter(geom_3857__intersects=aoi_shape.geom_3857).values_list('quadkey', flat=True)
        quadkeys.update(list(_quadkeys))

    quadkeys = list(quadkeys)
    if len(quadkeys) > 0:
        kwargs = {'quadkey': quadkeys}
        group_job = group(task_discover_listings_at_grid.s(quadkey=qk) for qk in quadkeys)
        group_result: AsyncResult = group_job.apply_async()

        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)

        group_task.op_name = op_discover_new_listings_at_aoi.name
        group_task.op_kwargs = kwargs
        group_task.save()

        return group_result.id


__all__ = ['op_discover_new_listings_at_grid', 'op_discover_new_listings_at_aoi',
           'op_discover_new_listings_periodical']
