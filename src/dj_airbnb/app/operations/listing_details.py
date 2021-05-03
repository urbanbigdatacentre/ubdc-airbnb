from typing import Union, List, Sequence, Collection, Optional

from celery import shared_task, group
from celery.result import GroupResult
from dateutil.relativedelta import relativedelta
from django.contrib.postgres.fields.jsonb import KeyTextTransform
from django.db.models import IntegerField, Subquery, Q, F, OuterRef
from django.db.models.functions import Cast
from django.utils.timezone import now

from app.errors import UBDCError
from app.models import UBDCGroupTask, UBDCGrid, AOIShape, AirBnBListing, UBDCTask
from app.operations.discovery import logger
from app.tasks import task_add_listing_detail


@shared_task
def op_add_listing_details_for_listing_ids(listing_id: Union[int, List[int]]) -> str:
    """ Fetch and store into the database LISTING DETAILS for one or many LISTING_IDs.
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
    group_result: GroupResult = job.apply_async()

    group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
    group_task.op_initiator = op_add_listing_details_for_listing_ids.name
    group_task.op_name = task_add_listing_detail.name
    group_task.op_kwargs = {'listing_id': listing_id}
    group_task.save()

    return group_result.id


@shared_task
def op_add_listing_details_at_grid(quadkey: Union[str, Collection[str]], ) -> Optional[str]:
    """ DESCRIPTION MISSING
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
        listings = list(grid.listings.values_list('listing_id', flat=True))
        listing_ids.update(listings)

    listing_ids = list(listing_ids)

    if len(listing_ids) > 0:
        job = op_add_listing_details_for_listing_ids.s(listing_id=listing_ids)
        result = job.apply_async()

        return result.id
    logger.info('No listings found to act upon')
    return


@shared_task
def op_add_listing_details_at_aoi(id_shape: Union[int, List[int]]) -> Optional[str]:
    """ Fetch and store into the database LISTING DETAILS for the LISTING_IDs found in the quad-grids
    intersecting with AOI ID_SHAPEs.

    This is an initiating task which will generate len(listing_id) sub tasks.

    Internally we are greedy; We identify the listings based on UBDCGrid, that intersect with the AOIShape.
    Therefore it could return NONE, if that AOIShape does not have any grid yet.

    :param id_shape: an integer or a List[int] of PK describing AOIShapes
    :returns str(UUID) of the group task containing the sub tasks
    """

    if hasattr(id_shape, '__iter__'):
        id_shapes = id_shape
    else:
        id_shapes = (id_shape,)

    quadkeys = set()
    for _id in id_shapes:
        aoi_shape = AOIShape.objects.get(id=_id)
        _quadkeys = list(
            UBDCGrid.objects.filter(geom_3857__intersects=aoi_shape.geom_3857).values_list('quadkey', flat=True))
        quadkeys.update(_quadkeys)

    quadkeys = list(quadkeys)
    if len(quadkeys) > 0:
        kwargs = {'quadkey': quadkeys}
        job = group(op_add_listing_details_at_grid.s(quadkey=quadkey) for quadkey in quadkeys)
        group_result = job.apply_async()
        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)

        group_task.op_initiator = op_add_listing_details_at_aoi.name
        group_task.op_name = op_add_listing_details_at_grid.name
        group_task.op_kwargs = kwargs
        group_task.save()

        return group_result.id

    logger.info(f'No quadkeys have been found for AOI Shapes: {id_shapes} to act upon')
    return


@shared_task
def op_update_listing_details_periodical(how_many: int = 5000, age_hours: int = 24 * 14, priority=4,
                                         use_aoi=True) -> \
        Optional[str]:
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

    if how_many < 0:
        raise UBDCError('The variable how_many must be larger than 0')
    if age_hours < 0:
        raise UBDCError('The variable age_days must be larger than 0')
    if not (0 < priority < 10 + 1):
        raise UBDCError('The variable priority must be between 1 than 10')

    expire_23hour_later = 23 * 60 * 60

    start_day_today = now().replace(hour=0, minute=0, second=0, microsecond=0)

    if use_aoi:
        logger.debug("Use AOI: True")
        qs_aoi = AOIShape.objects.filter(collect_listing_details=True, geom_3857__intersects=OuterRef('geom_3857'))[:1]
        qs_listings = AirBnBListing.objects.filter(
            geom_3857__intersects=Subquery(qs_aoi.values('geom_3857')))
        logger.info(f"Found {qs_listings.count()} listings")
    else:
        logger.info("Use AOI: False")
        qs_listings = AirBnBListing.objects.all()

    excluded_listings = (UBDCTask.objects
                         .filter(datetime_submitted__gte=start_day_today - relativedelta(days=1))
                         .filter(task_name=task_add_listing_detail.name)
                         .filter(status=UBDCTask.TaskTypeChoices.SUBMITTED)
                         .filter(task_kwargs__has_key='listing_id')
                         .annotate(listing_ids=Cast(KeyTextTransform('listing_id', 'task_kwargs'), IntegerField())))
    logger.info(f"Excluded Listings  {excluded_listings.count()}")

    qs_listings = (qs_listings
                   .exclude(listing_id__in=Subquery(excluded_listings.values_list('listing_ids', flat=True)))
                   .filter(
        Q(listing_updated_at__lt=start_day_today - relativedelta(hours=age_hours)) |
        Q(listing_updated_at__isnull=True)
    ).order_by(F('listing_updated_at').asc(nulls_first=True)))

    if qs_listings.exists():
        listing_ids = list(qs_listings.values_list('listing_id', flat=True)[:how_many])
        logger.info(f"Found {len(listing_ids)} listing ids for collection")
        job = group(task_add_listing_detail.s(listing_id=listing_id) for listing_id in listing_ids)
        group_result: GroupResult = job.apply_async(priority=priority, expires=expire_23hour_later)

        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
        group_task.op_initiator = op_update_listing_details_periodical.name
        group_task.op_name = task_add_listing_detail.name
        group_task.op_kwargs = {'listing_id': listing_ids}
        group_task.save()

        return group_result.id
    return None
