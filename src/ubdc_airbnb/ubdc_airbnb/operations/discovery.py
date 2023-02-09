from typing import List, Sequence, Union

from celery import group, shared_task
from celery.result import GroupResult, AsyncResult
from celery.utils.log import get_task_logger
from dateutil.relativedelta import relativedelta
from django.db.models import TextField, F
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast
from django.utils.timezone import now

from ubdc_airbnb.errors import UBDCError
from ubdc_airbnb.models import UBDCGroupTask, UBDCTask, UBDCGrid, AOIShape
from ubdc_airbnb.tasks import task_discover_listings_at_grid
from ubdc_airbnb.utils.spatial import get_grids_for

logger = get_task_logger(__name__)


@shared_task
def op_discover_new_listings_at_grid(quadkey: Union[str, List[str]]) -> str:
    """Add the calendars for the listings_id that are in this AOI to the database

    :param quadkey: Quadkey or quadkeys to search
    :returns: ..."""

    if isinstance(quadkey, Sequence) and not isinstance(quadkey, str):
        _quadkeys = quadkey
    else:
        _quadkeys = [
            quadkey,
        ]

    job = group(task_discover_listings_at_grid.s(quadkey=_qk) for _qk in _quadkeys)
    group_result = job.apply_async()

    group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)

    group_task.op_name = op_discover_new_listings_at_grid.name
    group_task.op_kwargs = {"quadkey": _quadkeys}
    group_task.save()

    return group_result.id


@shared_task
def op_discover_new_listings_periodical(
    how_many: int = 500,
    age_hours: int = 7 * 24,
    use_aoi: bool = True,
    priority=4,
) -> str:
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
        raise UBDCError("The variable how_many must be larger than 0")
    if age_hours < 0:
        raise UBDCError("The variable age_days must be larger than 0")
    if not (0 < priority < 10 + 1):
        raise UBDCError("The variable priority must be between 1 than 10")

    how_many = int(how_many)
    age_hours = int(age_hours)
    priority = int(priority)

    start_day_today = now().replace(hour=0, minute=0, second=0, microsecond=0)

    q_quadkeys = UBDCGrid.objects.all()
    logger.info(f"number of all Grids: {q_quadkeys.count()}")
    if use_aoi:
        q_quadkeys = get_grids_for("discover_listings")
        logger.info(f"Using AOIs")
        logger.info(f"Using {q_quadkeys.count()}")
    threshold = start_day_today - relativedelta(days=1)
    engaged_qk = (
        UBDCTask.objects.filter(datetime_submitted__gte=threshold)
        .filter(task_name=task_discover_listings_at_grid.name)
        .filter(task_kwargs__has_key="quadkey")
        .annotate(quadkey=Cast(KeyTextTransform("quadkey", "task_kwargs"), TextField()))
        .order_by("quadkey")
        .distinct("quadkey")
        .values("quadkey")
    )
    qs_qk = q_quadkeys.exclude(quadkey__in=engaged_qk)
    logger.info(f"QK: After Removing Excluded: {qs_qk.count()}")

    threshold = (start_day_today - relativedelta(days=age_hours)).date()
    qs_quadkeys = (
        UBDCGrid.objects.filter(quadkey__in=qs_qk)
        .filter(datetime_last_listings_scan__lte=threshold)
        .order_by(F("datetime_last_listings_scan").asc(nulls_first=True))
    )
    logger.info(f"After excluded: {qs_quadkeys.count()}")
    qs_quadkeys = qs_quadkeys[0:how_many]
    logger.info(f"Final selection: {qs_quadkeys.count()}")

    if qs_quadkeys.exists():
        quadkeys = list(qs_quadkeys.values_list("quadkey", flat=True))
        job = group(
            task_discover_listings_at_grid.s(
                quadkey=qk,
            )
            for qk in quadkeys
        )
        group_result: GroupResult = job.apply_async(
            priority=priority,
        )

        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
        group_task.op_name = op_discover_new_listings_periodical.name
        group_task.op_kwargs = {"quadkey": quadkeys}
        group_task.save()

        return group_result.id
    return "nothing"


@shared_task
def op_discover_new_listings_at_aoi(id_shape: Union[int, List[int]]) -> str:
    """Add the calendars for the listings_id that are in this AOI to the database
    :param id_shape: pk of ::AOIShape::
    """

    if isinstance(id_shape, Sequence):
        id_shapes = id_shape
    else:
        id_shapes = (id_shape,)

    quadkeys = set()
    for _id in id_shapes:
        aoi_shape = AOIShape.objects.get(id=_id)
        _quadkeys = UBDCGrid.objects.filter(geom_3857__intersects=aoi_shape.geom_3857).values_list("quadkey", flat=True)
        quadkeys.update(list(_quadkeys))

    quadkeys = list(quadkeys)
    if len(quadkeys) > 0:
        kwargs = {"quadkey": quadkeys}
        group_job = group(task_discover_listings_at_grid.s(quadkey=qk) for qk in quadkeys)
        group_result: AsyncResult = group_job.apply_async()

        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)

        group_task.op_name = op_discover_new_listings_at_aoi.name
        group_task.op_kwargs = kwargs
        group_task.save()

        return group_result.id


__all__ = [
    "op_discover_new_listings_at_grid",
    "op_discover_new_listings_at_aoi",
    "op_discover_new_listings_periodical",
]
