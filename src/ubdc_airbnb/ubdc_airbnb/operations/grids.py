from typing import List, Optional, Sequence, Union

from celery import group, shared_task
from celery.result import AsyncResult, GroupResult
from dateutil.relativedelta import relativedelta
from django.db.models import BooleanField, F, OuterRef, Q, Subquery, TextField
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast
from django.utils import timezone

from ubdc_airbnb.errors import UBDCError
from ubdc_airbnb.models import AOIShape, UBDCGrid, UBDCGroupTask, UBDCTask
from ubdc_airbnb.tasks import task_register_listings_or_divide_at_qk
from ubdc_airbnb.utils.time import seconds_from_now


@shared_task
def op_estimate_listings_or_divide_at_grid(
    quadkey: Union[str, List[str]],
    less_than=50,
    priority=4,
) -> str:
    """Queries AirBNB end point and asks how many listings exist in that grid. if more than 'less_than' then divide.
    Warning. Generates tasks.

    :param priority:
    :param quadkey: list of quadkey strings to estimate or divide
    :param less_than: threshold number of limits to divide, optional default 50

    :returns: group_task uuid
    :rtype: str
    """

    # if not a list
    if not (isinstance(quadkey, Sequence) and not isinstance(quadkey, str)):
        _quadkeys = [
            quadkey,
        ]
    else:
        _quadkeys = quadkey

    job = group(task_register_listings_or_divide_at_qk.s(quadkey=qk, less_than=less_than) for qk in _quadkeys)
    group_result: AsyncResult[GroupResult] = job.apply_async(priority=priority)
    group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)

    group_task.op_name = op_estimate_listings_or_divide_at_grid.name
    group_task.op_kwargs = {"quadkey": quadkey}
    group_task.save()

    return group_result.id


@shared_task
def op_estimate_listings_or_divide_at_aoi(
    aoi_id: int,
    less_than=50,
) -> str:
    """**Note: Only one aoi_id. Queries grids using AirBNB end point to identify how many listings exist in that grid.
    If more than 'less_than' listings return for that grid then we divide (using a task).

    :param aoi_id: aoi
    :param less_than: threshold number of limits to divide, optional default 50

    :returns: group_task uuid
    :rtype: str
    """

    aoi_shape = AOIShape.objects.get(id=aoi_id)
    grids = UBDCGrid.objects.filter(geom_3857__intersects=aoi_shape.geom_3857)
    quadkeys = list(grids.values_list("quadkey", flat=True))

    task = op_estimate_listings_or_divide_at_grid.s(quadkey=quadkeys, less_than=less_than)
    task_result: AsyncResult = task.apply_async()

    return task_result.id


@shared_task
def op_estimate_listings_or_divide_periodical(
    how_many: int = 500,
    age_hours: int = 14 * 24,
    use_aoi: bool = False,
    max_listings=50,
    priority=4,
) -> Optional[str]:
    """
    An 'initiator' task that will select at the most 'how_many' (default 500) Grids had not been scanned for
    new listings for more than 'age_days' (default 14) days.
        For each of these grids a task will be created with priority 'priority' (default 4).
        These tasks then will  proceed to check the grid if it has more than 'max_listings' (default 50).
        If it has it will then split it in 4 sub-grids, and for each sub-grid a new task will be published to repeat the operation
        Any task generated from here is  hard-coded to expire, if not completed, in 23 hours after it was  published.

    Return is a task_group_id UUID string that  these tasks will operate under.
    In case there are no listings found None will be returned instead

    :param max_listings: Maximum
    :param use_aoi: use grids that intersect with AOI.
    :param how_many:  Maximum number of listings to act, defaults to 5000.
    :param age_hours: How many DAYS before from the last update, before the it will be considered stale. int > 0, defaults to 14 (two weeks).
                      Enter -1 to ignore the age restriction
    :param priority:  priority of the tasks generated. int from 1 to 10, 10 being maximum. defaults to 4
    :return: str(UUID)
    """

    how_many = int(how_many)
    age_hours = int(age_hours)
    priority = int(priority)

    if how_many < 0:
        raise UBDCError("The variable how_many must be larger than 0")
    if age_hours < 0:
        raise UBDCError("The variable age_days must be larger than 0 or -1")
    # TODO: Deprecate priority
    if not (0 < priority < 10 + 1):
        raise UBDCError("The variable priority must be between 1 than 10")

    expires = seconds_from_now(60 * 60 * 23)  # 23 hours
    start_day_today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    future_qk = (
        UBDCTask.objects.filter(
            datetime_submitted__gte=start_day_today - relativedelta(days=1)
        )  # datetime_submitted has index on it
        .filter(task_name=task_register_listings_or_divide_at_qk.name)
        .filter(status=UBDCTask.TaskTypeChoices.SUBMITTED)
        .filter(task_kwargs__has_key="quadkey")
        .annotate(quadkey=Cast(KeyTextTransform("quadkey", "task_kwargs"), TextField()))
    )

    if use_aoi:
        quadkeys_qs = UBDCGrid.objects.annotate(
            in_active_aoi=Subquery(
                AOIShape.objects.filter(
                    geom_3857__intersects=OuterRef("geom_3857"),
                    scan_for_new_listings=True,
                ).values("scan_for_new_listings")[:1],
                output_field=BooleanField(),
            )
        ).filter(in_active_aoi=True)

    else:
        quadkeys_qs = UBDCGrid.objects.all()

    quadkeys_qs = (
        quadkeys_qs.exclude(quadkey__in=Subquery(future_qk.values_list("quadkey", flat=True)))
        .filter(
            Q(datetime_last_estimated_listings_scan__lte=start_day_today - relativedelta(hours=age_hours))
            | Q(datetime_last_estimated_listings_scan__isnull=True)
        )
        .order_by(F("datetime_last_estimated_listings_scan").asc(nulls_first=True))
    )

    if quadkeys_qs.exists():
        quadkeys = list(quadkeys_qs.values_list("quadkey", flat=True)[0:how_many])
        job = group(
            task_register_listings_or_divide_at_qk.s(quadkey=quadkey, less_than=max_listings)
            .set(priority=priority)  # TODO: Deprecate priority
            .set(expires=expires)
            for quadkey in quadkeys
        )
        group_result: AsyncResult[GroupResult] = job.apply_async(priority=priority)
        group_result.save()

        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
        group_task.op_name = task_register_listings_or_divide_at_qk.name
        group_task.op_initiator = op_estimate_listings_or_divide_periodical.name
        group_task.op_kwargs = {"quadkey": quadkeys}
        group_task.save()

        return group_result.id
    return None


__all__ = [
    "op_estimate_listings_or_divide_at_grid",
    "op_estimate_listings_or_divide_at_aoi",
    "op_estimate_listings_or_divide_periodical",
]
