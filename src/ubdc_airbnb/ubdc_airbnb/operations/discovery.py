from typing import List, Sequence, Union

from celery import group, shared_task
from celery.result import AsyncResult, GroupResult
from celery.utils.log import get_task_logger
from dateutil.relativedelta import relativedelta
from django.db.models import F, TextField
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast
from django.utils.timezone import now

from ubdc_airbnb.errors import UBDCError
from ubdc_airbnb.models import AOIShape, UBDCGrid, UBDCGroupTask, UBDCTask
from ubdc_airbnb.tasks import task_discover_listings_at_grid
from ubdc_airbnb.utils.spatial import get_quadkeys_for

logger = get_task_logger(__name__)


@shared_task
def op_discover_new_listings_at_grid(
    quadkey: Union[str, List[str]],
) -> str:
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
def op_discover_new_listings_periodical() -> str | None:
    """
    An 'initiator' task that will start the process of discovering new listings in the AOIs that are marked for this task.
    There's no expiration date for this task.
    Return is a task_group_id UUID string that these tasks will operate under.
    """

    from ubdc_airbnb.tasks import task_register_listings_or_divide_at_quadkey

    aois = list(AOIShape.objects.filter(scan_for_new_listings=True))

    grids = UBDCGrid.objects.intersect_with_aoi(aois)

    if grids.exists():
        job = group(
            task_register_listings_or_divide_at_quadkey.s(quadkey=grid.quadkey)
            for grid in grids.iterator(chunk_size=1000)
        )
        group_result: AsyncResult[GroupResult] = job.apply_async()
        group_result.save()  # type: ignore
        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)

        group_task.op_name = op_discover_new_listings_periodical.name
        group_task.save()

        return group_result.id

    logger.info("No grids found for active AOIs to search")


@shared_task
def op_discover_new_listings_at_aoi(
    id_shape: Union[int, List[int]],
) -> str | None:
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
        group_result: AsyncResult[GroupResult] = group_job.apply_async()
        group_result.save()  # type: ignore

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
