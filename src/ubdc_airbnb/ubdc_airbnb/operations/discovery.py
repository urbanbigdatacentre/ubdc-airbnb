from celery import group, shared_task
from celery.result import AsyncResult, GroupResult
from celery.utils.log import get_task_logger
from django.conf import settings

from ubdc_airbnb.models import AOIShape, UBDCGrid, UBDCGroupTask

logger = get_task_logger(__name__)


@shared_task(acks_late=False)
def op_discover_new_listings_periodical() -> str | None:
    """
    An 'initiator' task that will start the process of discovering new listings in the active AOIs.

    Return value is the correlation ID of the group task that was created to handle the discovery process.
    """

    from ubdc_airbnb.tasks import task_register_listings_or_divide_at_quadkey

    aois = list(AOIShape.objects.filter(scan_for_new_listings=True))

    grids = UBDCGrid.objects.intersect_with_aoi(aois)
    quadkeys = grids.values_list("quadkey", flat=True)

    def submit_batch(batch: list[str]):
        job = group(task_register_listings_or_divide_at_quadkey.s(quadkey=qk) for qk in batch)
        group_result: AsyncResult[GroupResult] = job.apply_async()
        group_result.save()  # type: ignore
        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)

        group_task.op_name = op_discover_new_listings_periodical.name
        group_task.save()
        logger.info(f"Sentch of {len(batch)} grids to task group {group_result.id}")

    chunk_size = settings.CELERY_TASK_CHUNK_SIZE
    if quadkeys.exists():
        batch = []
        for idx, qk in enumerate(quadkeys.iterator(chunk_size=chunk_size)):
            batch.append(qk)
            if idx % chunk_size == 0 and idx > 0:
                submit_batch(batch)
                batch.clear()
        submit_batch(batch)
        return

    logger.info("No grids found for active AOIs to search")


__all__ = [
    "op_discover_new_listings_periodical",
]
