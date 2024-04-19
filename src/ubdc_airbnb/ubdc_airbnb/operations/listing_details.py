from datetime import timedelta
from typing import TYPE_CHECKING, Collection, List, Optional, Sequence, Union

from celery import group, shared_task
from celery.result import AsyncResult, GroupResult, ResultSet
from celery.utils.log import get_task_logger
from django.db.models import F
from django.utils.timezone import now

from ubdc_airbnb.errors import UBDCError
from ubdc_airbnb.models import AirBnBListing, AOIShape, UBDCGrid, UBDCGroupTask
from ubdc_airbnb.tasks import task_get_listing_details
from ubdc_airbnb.utils.spatial import get_listings_qs_for_aoi
from ubdc_airbnb.utils.tasks import get_submitted_listing_ids_for

logger = get_task_logger(__name__)

if TYPE_CHECKING:
    from django.db.models import QuerySet


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


@shared_task
def op_add_listing_details_at_grid(
    quadkey: Union[str, Collection[str]],
) -> Optional[str]:
    """DESCRIPTION MISSING
    :param quadkey: quadkey
    :returns: GroupResult uuid
    :rtype: str
    """

    # if not a list
    if isinstance(quadkey, Sequence) and not isinstance(quadkey, str):
        _quadkeys = quadkey
    else:
        _quadkeys = (quadkey,)
    grids = UBDCGrid.objects.filter(quadkey__in=_quadkeys)

    listing_ids = set()
    for grid in grids:
        listings = list(grid.listings.values_list("listing_id", flat=True))
        listing_ids.update(listings)

    listing_ids = list(listing_ids)

    logger.info(f"Listing IDs found: {listing_ids}")
    if len(listing_ids) > 0:
        job = op_add_listing_details_for_listing_ids.s(listing_id=listing_ids)
        result = job.apply_async()

        return result.id
    return


@shared_task(acks_late=False)
def op_add_listing_details_at_aoi(
    id_shapes: Union[int, List[int]],
) -> Optional[str]:
    """Fetch and store into the database LISTING DETAILS for the LISTING_IDs found in the quad-grids
    intersecting with AOI ID_SHAPEs.

    This is an initiating task which will generate len(listing_id) sub tasks.

    Internally we are greedy; We identify the listings based on UBDCGrid, that intersect with the AOIShape.
    Therefore it could return NONE, if that AOIShape does not have any grid yet.

    :param id_shape: an integer or a List[int] of PK describing AOIShapes
    :returns str(UUID) of the group task containing the sub tasks
    """

    if isinstance(id_shapes, int):
        id_shapes = [
            id_shapes,
        ]

    quadkeys = set()
    for _id in id_shapes:
        aoi_shape = AOIShape.objects.get(id=_id)
        _quadkeys = list(
            UBDCGrid.objects.filter(geom_3857__intersects=aoi_shape.geom_3857).values_list("quadkey", flat=True)
        )
        quadkeys.update(_quadkeys)

    quadkeys = list(quadkeys)
    if len(quadkeys) > 0:
        kwargs = {"quadkey": quadkeys}
        job = group(op_add_listing_details_at_grid.s(quadkey=quadkey) for quadkey in quadkeys)
        group_result: AsyncResult[GroupResult] = job.apply_async()
        group_result.save()  # type: ignore

        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)

        group_task.op_initiator = op_add_listing_details_at_aoi.name
        group_task.op_name = op_add_listing_details_at_grid.name
        group_task.op_kwargs = kwargs
        group_task.save()

        return group_result.id

    logger.info(f"No quadkeys have been found for AOI Shapes: {id_shapes} to act upon")
    return


@shared_task(acks_late=False)
def op_update_listing_details_periodical(use_aoi=True) -> Optional[str]:
    """Fetch listing details.
    If use_aoi = True (default) it will only fetch for listings that intersect with AOIs that are marked for such."""

    logger.info(f"Using AOI: {use_aoi}")

    listings_qs = AirBnBListing.objects.all()
    if use_aoi:
        listings_qs = get_listings_qs_for_aoi("listing_details")

    logger.info(f"Found {listings_qs.count()} listings to fetch.")
    if listings_qs.exists():
        listing_ids = listings_qs.values_list("listing_id", flat=True)
        job = group(task_get_listing_details.s(listing_id=listing_id) for listing_id in listing_ids)
        group_result: AsyncResult[GroupResult] = job.apply_async()
        group_result.save()  # type: ignore
        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
        group_task.op_initiator = op_update_listing_details_periodical.name
        group_task.op_name = task_get_listing_details.name
        group_task.op_kwargs = {"listing_id": listing_ids}
        group_task.save()

        return group_result.id

    logger.info(f"No listings for listing_details have been found!")
    return None


__all__ = [
    "op_update_listing_details_periodical",
]
