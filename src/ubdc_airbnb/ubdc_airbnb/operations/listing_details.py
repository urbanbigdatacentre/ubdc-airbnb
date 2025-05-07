from typing import List, Optional, Sequence, Union

from celery import group, shared_task
from celery.result import AsyncResult, GroupResult
from celery.utils.log import get_task_logger
from django.conf import settings

from ubdc_airbnb.models import AirBnBListing, UBDCGroupTask
from ubdc_airbnb.tasks import task_get_listing_details

logger = get_task_logger(__name__)


@shared_task
def op_add_listing_details_for_listing_ids(
    listing_id: Union[int, List[int]],
) -> str:
    """Fetch and store LISTING DETAILS for one or many LISTING_IDs.
    This is an initiating task which will generate len(listing_id) sub tasks.

    :param listing_id: an integer or a List[int] to get the listing details from airbnb
    :returns str(UUID) of the group task containing the sub tasks
    """

    if isinstance(listing_id, str) or isinstance(listing_id, int):
        _listing_ids = (listing_id,)
    else:
        _listing_ids = listing_id

    if isinstance(listing_id, Sequence):
        _listing_ids = map(int, listing_id)

    job = group(task_get_listing_details.s(listing_id=listing_id) for listing_id in _listing_ids)
    group_result = job.apply_async()
    group_result.save()  # type: ignore # TODO: fix typing

    group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
    group_task.op_initiator = op_add_listing_details_for_listing_ids.name
    group_task.op_name = task_get_listing_details.name
    group_task.op_kwargs = {"listing_id": listing_id}
    group_task.save()

    return group_result.id


@shared_task(acks_late=False)
def op_update_listing_details_periodical(use_aoi=True) -> Optional[str]:
    """Fetch listing details.
    If use_aoi = True (default) it will only fetch for listings that intersect with AOIs that are marked for such."""

    logger.info(f"Using AOI: {use_aoi}")
    if use_aoi:
        listings_qs = AirBnBListing.objects.for_purpose("listing_details")
    else:
        listings_qs = AirBnBListing.objects.all()

    def process_group(batch):
        job = group(task_get_listing_details.s(listing_id=listing_id) for listing_id in batch)
        group_result: AsyncResult[GroupResult] = job.apply_async()
        group_result.save()  # type: ignore
        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
        group_task.op_initiator = op_update_listing_details_periodical.name
        group_task.op_name = task_get_listing_details.name
        group_task.op_kwargs = {"listing_id": batch}
        group_task.save()

    logger.info(f"Found {listings_qs.count()}.")
    chunk_size = settings.CELERY_TASK_CHUNK_SIZE
    if listings_qs.exists():
        listing_ids = listings_qs.values_list("listing_id", flat=True)
        batch = []
        for idx, listing_id in enumerate(listing_ids.iterator(chunk_size=chunk_size)):
            batch.append(listing_id)
            if idx % chunk_size == 0 and idx > 0:
                process_group(batch)
                batch.clear()
        # process the last batch
        process_group(batch)

        return
    logger.info(f"No listings for listing_details have been found!")
    return


__all__ = [
    "op_update_listing_details_periodical",
]
