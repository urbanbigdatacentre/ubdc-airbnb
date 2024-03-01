from datetime import timedelta
from typing import TYPE_CHECKING, Collection, List, Optional, Sequence, Union

from celery import group, shared_task
from celery.result import AsyncResult, GroupResult
from celery.utils.log import get_task_logger
from django.db.models import F
from django.utils.timezone import now

from ubdc_airbnb.errors import UBDCError
from ubdc_airbnb.models import AirBnBListing, AOIShape, UBDCGrid, UBDCGroupTask
from ubdc_airbnb.tasks import task_add_listing_detail
from ubdc_airbnb.utils.spatial import get_listings_qs_for_aoi
from ubdc_airbnb.utils.tasks import get_submitted_listing_ids_for

logger = get_task_logger(__name__)

if TYPE_CHECKING:
    from django.db.models import QuerySet


@shared_task
def op_add_listing_details_for_listing_ids(
    listing_id: Union[int, List[int]],
) -> str:
    """Fetch and store into the database LISTING DETAILS for one or many LISTING_IDs.
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

    job = group(task_add_listing_detail.s(listing_id=listing_id) for listing_id in _listing_ids)
    group_result: AsyncResult[GroupResult] = job.apply_async()
    group_result.save()

    group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
    group_task.op_initiator = op_add_listing_details_for_listing_ids.name
    group_task.op_name = task_add_listing_detail.name
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


@shared_task
def op_add_listing_details_at_aoi(
    id_shape: Union[int, List[int]],
) -> Optional[str]:
    """Fetch and store into the database LISTING DETAILS for the LISTING_IDs found in the quad-grids
    intersecting with AOI ID_SHAPEs.

    This is an initiating task which will generate len(listing_id) sub tasks.

    Internally we are greedy; We identify the listings based on UBDCGrid, that intersect with the AOIShape.
    Therefore it could return NONE, if that AOIShape does not have any grid yet.

    :param id_shape: an integer or a List[int] of PK describing AOIShapes
    :returns str(UUID) of the group task containing the sub tasks
    """

    if hasattr(id_shape, "__iter__"):
        id_shapes = id_shape
    else:
        # if not a list
        id_shapes = (id_shape,)

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
        group_result.save()

        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)

        group_task.op_initiator = op_add_listing_details_at_aoi.name
        group_task.op_name = op_add_listing_details_at_grid.name
        group_task.op_kwargs = kwargs
        group_task.save()

        return group_result.id

    logger.info(f"No quadkeys have been found for AOI Shapes: {id_shapes} to act upon")
    return


@shared_task
def op_update_listing_details_periodical(
    how_many: int = 5000, age_hours: int = 24 * 14, priority=4, use_aoi=True
) -> Optional[str]:
    """
    An 'initiator' task that will select at the most 'how_many' (default 5000) listings that their listing details
    are older than 'age_days' (default 15) days old.
        For each of these listing a task will be created with priority 'priority' (default 4).
        The tasks are hard-coded to expire, if not completed, in 23 hours after their publication

    Return is a task_group_id UUID string that  these tasks will operate under.
    In case there are no listings found None will be returned instead

    :param use_aoi: If true, the listings will be selected only from the aoi_shapes that have been designated to this task, default  true
    :param how_many:  Maximum number of listings to act, defaults to 5000
    :param age_hours: How many HOURS before from the last update, before the it will be considered stale. int > 0, defaults to 14 (two weeks)
    :param priority:  priority of the tasks generated. int from 1 to 10, 10 being maximum. defaults to 4
    :return: str(UUID)
    """
    how_many = int(how_many)
    age_hours = int(age_hours)
    priority = int(priority)

    if how_many < 0:
        raise UBDCError("The variable how_many must be larger than 0")
    if age_hours < 0:
        raise UBDCError("The variable age_days must be larger than 0")
    if not (0 < priority <= 10):
        raise UBDCError("The variable priority must be between 1 than 10")

    logger.info(f"Using AOI: {use_aoi}")
    if use_aoi:
        qs_listings = get_listings_qs_for_aoi("listing_details")
    else:
        qs_listings: QuerySet = AirBnBListing.objects.all()

    logger.info(f"Found {qs_listings.count()} listings")

    engaged_listings = get_submitted_listing_ids_for(purpose="listing_details")
    qs_listing_ids = qs_listings.exclude(listing_id__in=engaged_listings).order_by("listing_id").distinct()

    timethrehold = (now() - timedelta(hours=age_hours)).date()

    qs_listings = (
        AirBnBListing.objects.filter(listing_id__in=qs_listing_ids)
        .filter(listing_updated_at__lte=timethrehold)
        .order_by(F("listing_updated_at").asc(nulls_first=True))
    )
    logger.info(
        f"Listing that are eligible to fetch their listings details: \t{qs_listings.count()}"
        f"But will limit the selection to upper bound of {how_many} listings."
    )
    qs_listings = qs_listings[:how_many]
    if qs_listings.exists():
        listing_ids = list(qs_listings.values_list("listing_id", flat=True))
        job = group(task_add_listing_detail.s(listing_id=listing_id) for listing_id in listing_ids)
        group_result: GroupResult = job.apply_async(priority=priority)

        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
        group_task.op_initiator = op_update_listing_details_periodical.name
        group_task.op_name = task_add_listing_detail.name
        group_task.op_kwargs = {"listing_id": listing_ids}
        group_task.save()

        return group_result.id
    logger.info(f"No listings for listing_details have been found!")
    return None


__all__ = [
    "op_update_listing_details_periodical",
]
