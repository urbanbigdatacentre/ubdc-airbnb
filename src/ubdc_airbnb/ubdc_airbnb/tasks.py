from collections import Counter
from datetime import timedelta
from random import random
from typing import TYPE_CHECKING, Optional, Union

import mercantile
from celery import Task, group, shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.contrib.gis.db.models import Extent
from django.contrib.gis.geos import Point
from django.contrib.gis.geos import Polygon as GEOSPolygon
from django.db import transaction
from django.db.models import Count, Max, Min, Sum
from django.db.models.functions import Length, Substr
from django.utils import timezone
from django.utils.timesince import timesince
from more_itertools import collapse
from requests import HTTPError
from requests.exceptions import ProxyError

from ubdc_airbnb.airbnb_interface.airbnb_api import AirbnbApi
from ubdc_airbnb.decorators import convert_exceptions
from ubdc_airbnb.errors import UBDCError, UBDCRetriableError
from ubdc_airbnb.models import (
    AirBnBListing,
    AirBnBResponse,
    AirBnBResponseTypes,
    AirBnBReview,
    AirBnBUser,
    UBDCGrid,
    UBDCGroupTask,
    UBDCTask,
)
from ubdc_airbnb.task_managers import BaseTaskWithRetry
from ubdc_airbnb.utils.grids import bbox_from_quadkey
from ubdc_airbnb.utils.spatial import listing_locations_from_response, reproject

logger = get_task_logger(__name__)
airbnb_client = AirbnbApi(proxy=settings.AIRBNB_PROXY)


if TYPE_CHECKING:
    from celery.result import GroupResult


@shared_task(bind=True)
@convert_exceptions
def task_update_or_add_reviews_at_listing(
    self: Task,
    listing_id: int,
    force_check: bool = False,
    **kwargs,
) -> str:
    """
    Fetches comments responses  inside the database for a particular listing.
    Adds any new users in the process.

    :param self: UBDCTask
    :type self: UBDCTask
    :param listing_id:  The listing_id of the listing that the comments/reviews will be harvested from
    :type listing_id: int
    :param force_check: ,defaults to True
    :type force_check: bool, optional
    :param defer_user_creation: Create a temporary AirBnB User entry and submit a task to populate data later.
                                Defaults to True


    :return: Returns the number of reviews that were processed.
    :rtype: int

    """

    # comment to fetch per request
    priority = int(kwargs.get("priority", 4))
    limit = int(kwargs.get("reviews_per_page", 100))
    if not 0 <= priority <= 10:
        raise UBDCError("Variable priority must be between 0 and 10")
    if not 1 < limit <= 100:
        raise UBDCError("Variable reviews_per_page must be between 1 and 100")

    task_id = self.request.id

    # summary of what we did
    _return = {
        "AirBnBListing": 0,
        "AirBnBReview": [],
    }

    listing = AirBnBListing.objects.get(listing_id=listing_id)

    # get the first page
    response_review = AirBnBResponse.objects.fetch_response(
        offset=0,
        limit=limit,
        type=AirBnBResponseTypes.review,
        listing_id=listing_id,
        task_id=task_id,
    )

    _return["AirBnBListing"] = response_review.id
    reviews_total_number = response_review.payload["metadata"]["reviews_count"]
    page = response_review.payload.copy()

    # Logic:
    # With each page fetched; check if the most recent reviews
    # for an existing listing (in the db)
    #
    # The reviews are coming in chronological order, timestamp desc. (newest first.)
    #  For each review:
    #   Check if we have the users, if not make a placeholder user

    reviews_seen = 0
    reviews_processed = []

    user_default = {
        "first_name": "UBDC-PLACEHOLDER",
        "airbnb_listing_count": 0,
        "verifications": [],
        "picture_url": "",
        "location": "",
    }

    while True:
        reviews = page["reviews"]
        reviews_seen += len(reviews)

        # for/else
        for review in reviews:
            review_id = review["id"]
            author_id = review["author_id"]
            recipient_id = review["recipient_id"]

            author, created = AirBnBUser.objects.get_or_create(user_id=author_id, defaults=user_default)
            if created:
                logger.info(f"Adding author user  ({author.user_id})")
            recipient, created = AirBnBUser.objects.get_or_create(user_id=recipient_id, defaults=user_default)
            if created:
                logger.info(f"Adding (recipient) user ({author.user_id})")
                # Connect author and recipient to this listing
            listing.users.add(author, recipient)

            try:
                review = AirBnBReview.objects.get(review_id=review_id)
                seen_before = True
            except AirBnBReview.DoesNotExist:
                review = AirBnBReview(
                    review_id=review_id,
                    created_at=review["created_at"],
                    review_text=review["comments"],
                    language=review.get("language", ""),
                    listing=listing,
                    author_id=author.user_id,
                    recipient_id=recipient.user_id,
                    response=response_review,
                )
                seen_before = False
                reviews_processed.append(review)

            if seen_before and not force_check:
                break

        else:
            # only executed if the previous loop did NOT break
            if reviews_seen >= reviews_total_number:
                break
            offset = reviews_seen
            response_review = AirBnBResponse.objects.fetch_response(
                task_id=task_id,
                listing_id=listing_id,
                type=AirBnBResponseTypes.review,
                offset=offset,
                limit=limit,
            )
            page = response_review.payload

            continue
        break  # this is only executed if the inner loop DID break

    AirBnBReview.objects.bulk_create(reviews_processed)
    listing.reviews_updated_at = timezone.now()
    listing.save()
    logger.info(
        f"Finished processed reviews for listing_id: {listing.listing_id} (added {len(reviews_processed)} reviews)."
    )
    return f"Finished Processing Reviews for {listing.listing_id}"


@shared_task(bind=True)
@convert_exceptions
def task_update_calendar(
    self: BaseTaskWithRetry,
    listing_id: int,
    months: int = 12,
) -> int:
    """Get a calendar for this listing_id and stores it in the database. Returns the listing_id

    :param listing_id: listing_id
    :param months: Up to this many months, optional defaults to 12
    :returns: listing_id
    """

    listing_entry, created = AirBnBListing.objects.get_or_create(listing_id=listing_id)
    logger.info(f"Listing: {listing_id} created: {created}")
    try:
        ubdc_response = AirBnBResponse.objects.fetch_response(
            type=AirBnBResponseTypes.calendar,
            calendar_months=months,
            task_id=self.request.id,
            listing_id=listing_id,
        )
        if ubdc_response:
            listing_entry.responses.add(ubdc_response)

    except ProxyError as exc:
        raise exc

    except HTTPError as exc:
        status_code = exc.response.status_code
        ubdc_response = exc.ubdc_response
        match status_code:
            case 403:
                # 403 Resource Unavailable
                # The task is successful, but the resource is not available
                logger.info(f"resource-unavailable: Listing_id: {listing_id}")
                pass
            case _:
                logger.info(f"Http/Proxy error: {ubdc_response.payload}")
                raise exc

    # https://docs.python.org/3/reference/compound_stmts.html#finally-clause
    finally:
        listing_entry.calendar_updated_at = timezone.now()
        listing_entry.save()

    return listing_entry.listing_id


@shared_task(bind=True)
@convert_exceptions
def task_get_booking_detail(self: Task, listing_id: int) -> int:
    """
    Get a booking detail for this listing_id using the latest calendar from the database.
    Returns the listing_id if operation was successful.
    """

    listing, created = AirBnBListing.objects.get_or_create(listing_id=listing_id)
    calendar: AirBnBResponse | None = (
        AirBnBResponse.objects.filter(listing_id=listing_id, _type=AirBnBResponseTypes.calendar)
        .order_by("timestamp")
        .first()
    )

    try:
        booking_response = AirBnBResponse.objects.fetch_response(
            listing_id=listing_id,
            calendar=calendar.payload,
            type=AirBnBResponseTypes.bookingQuote,
            task_id=self.request.id,
        )
        if booking_response:
            listing.responses.add(booking_response)
    except HTTPError as exc:
        raise exc

    # https://docs.python.org/3/reference/compound_stmts.html#finally-clause
    finally:
        listing.booking_quote_updated_at = timezone.now()
        listing.save()

    logger.info(f"BookingQuote:LISTING_ID:{listing_id}:SUCCESS")
    return listing.listing_id


@shared_task(bind=True)
@convert_exceptions
def task_discover_listings_at_grid(
    self,
    quadkey: str,
):
    """Queries airbnb for listings in the given grid. Airbnb will return a maximum of 300 listings per request, so make sure that the grid is not too big.
    :param quadkey: quadkey
    """

    task_id = self.request.id

    try:
        tile = UBDCGrid.objects.get(quadkey=quadkey)
    except UBDCGrid.DoesNotExist as exc:
        logger.info(f"Grid {quadkey} does not exist. Aborting.")
        return

    west, south, east, north = list(mercantile.bounds(mercantile.quadkey_to_tile(tile.quadkey)))
    data_pages_gen = airbnb_client.iterate_homes(west=west, south=south, east=east, north=north)

    for page, _ in data_pages_gen:
        airbnbapi_response = airbnb_client.response
        logger.warning
        search_response_obj = AirBnBResponse.objects.create_from_response(
            airbnbapi_response, type=AirBnBResponseTypes.search, task_id=task_id
        )

        listings = listing_locations_from_response(airbnbapi_response.json())

        def add_listing_to_database(listing_id: str, point: Point):
            # point is in EPSG: 4326
            point_3857 = reproject(point, to_srid=3857)  # to measure any Δ distance in m
            listing, created = AirBnBListing.objects.get_or_create(listing_id=listing_id)
            if created:
                # it's a new listing. So don't bother checking if it was moved.
                listing.geom_3857 = point_3857
            else:
                distance = point_3857.distance(listing.geom_3857)

                # Check if the listing has been moved since last check more than the threshold
                move_threshold = float(settings.AIRBNB_LISTINGS_MOVED_MIN_DISTANCE)

                if distance > move_threshold:
                    # if it has, update the listing and add a note
                    msg = f"Listing ({listing_id}) have been moved since last check more than the threshold ({distance} vs {move_threshold})."
                    logger.info(msg)
                    key = timezone.now().isoformat()
                    root: dict = listing.notes
                    root[key] = {
                        "move": {
                            "from": listing.geom_3857.wkt,
                            "to": point_3857.wkt,
                            "distance": distance,
                        }
                    }
                    listing.geom_3857 = point_3857
            listing.save()

        listing_id: str
        point: Point
        for listing_id, point in listings.items():
            add_listing_to_database(listing_id, point)

        search_response_obj.grid = tile
        search_response_obj.save()

    tile.datetime_last_listings_scan = timezone.now()
    tile.save()
    return


@shared_task(bind=True)
@convert_exceptions
def task_get_listing_details(
    self,
    listing_id: Union[str, int],
) -> int:
    "Fetches the Listing Details for known ListingID. Returns the listing_id on success."

    # from this response we can harverst listing details and information if the host is a superhost or not.
    # I don't have a dedicated listing details model to populate

    task_id = self.request.id or None
    time_now = timezone.now()
    listing_id_int = int(listing_id)

    listing: AirBnBListing = AirBnBListing.objects.get(listing_id=listing_id_int)

    try:
        airbnb_response: AirBnBResponse = AirBnBResponse.objects.fetch_response(
            listing_id=listing_id_int,
            task_id=task_id,
            type=AirBnBResponseTypes.listingDetail,
        )
    except HTTPError as exc:
        raise exc
    finally:
        listing.listing_updated_at = time_now
        listing.save()

    listing.responses.add(airbnb_response)

    from ubdc_airbnb.utils.json_parsers import airbnb_response_parser

    pattern_primary_host = r"$..primary_host"
    pattern_additional_hosts = r"$..additional_hosts[*]"
    payload: dict = airbnb_response.payload
    primary_hosts_generator = airbnb_response_parser.generic(pattern_primary_host, payload)
    additional_hosts_generator = airbnb_response_parser.generic(pattern_additional_hosts, payload)

    from itertools import chain

    # process hosts
    for host in chain(primary_hosts_generator, additional_hosts_generator):
        user_id = host["id"]
        is_superhost = host.get("is_superhost", False)
        user, created = AirBnBUser.objects.get_or_create(user_id=user_id)
        user.is_superhost = is_superhost
        user.save()

    return listing_id_int


@shared_task(bind=True)
@convert_exceptions
def task_register_listings_or_divide_at_quadkey(
    self: BaseTaskWithRetry,
    quadkey: str,
) -> Optional[str]:
    """
    This task will query airbnb and get how many listings are in this grid.
    If the query comes back as paginated, it will split the grid into children and apply the same logic to each.
    If its not paginated, it will store the listings_id for the grid and return the group_result id.

    :returns: GroupResult uuid
    :rtype: str
    """

    # Easy to follow,
    # check bbox, if it's paginated, divide and resubmit
    # if not, store the listings
    from uuid import uuid4

    from ubdc_airbnb.utils.grids import clean_quadkeys, replace_quadkey_with_children
    from ubdc_airbnb.utils.json_parsers import airbnb_response_parser
    from ubdc_airbnb.workunits import (
        bbox_has_next_page,
        register_listings_from_response,
    )

    task_id = self.request.id or str(uuid4())
    grid: UBDCGrid = UBDCGrid.objects.get(quadkey=quadkey)
    bbox = bbox_from_quadkey(grid.quadkey)

    east = bbox.east
    north = bbox.north
    south = bbox.south
    west = bbox.west

    response_pk, has_next_page = bbox_has_next_page(
        east=east,
        north=north,
        south=south,
        west=west,
        task_id=task_id,
    )

    grid.datetime_last_estimated_listings_scan = timezone.now()
    if has_next_page:
        logger.info(f"Grid {grid.quadkey} has multiple pages of listings. Dividing!")
        quadkey = grid.quadkey
        children_quadkeys = replace_quadkey_with_children(quadkey)
        job = group(task_register_listings_or_divide_at_quadkey.s(quadkey=qk) for qk in children_quadkeys)
        group_result = job.apply_async()
        group_task = UBDCGroupTask.objects.get(group_task_id=group_result.id)
        group_task.op_name = task_register_listings_or_divide_at_quadkey.name
        group_task.op_kwargs = {"quadkey": children_quadkeys}
        group_task.save()

        return group_result.id

    # The grid is not paginated
    # Get the payload this task_id has generated; and add additional.
    response: AirBnBResponse = AirBnBResponse.objects.get(pk=response_pk)
    payload = response.payload
    listings = register_listings_from_response(payload)
    estimated_listings = airbnb_response_parser.listing_count(payload)
    grid.estimated_listings = estimated_listings
    logger.info(f"Grid {grid.quadkey} has {grid.estimated_listings} listings.")
    grid.datetime_last_listings_scan = timezone.now()
    grid.save()

    # TODO: Not Implemented:
    # There's an oportunity here to extract the primary hosts
    # from the found listings on this grid.

    # associate the response with the grids.
    for listing in listings:
        listing.responses.add(response)

    return None


@shared_task(bind=True)
@convert_exceptions
def task_update_user_details(
    self: BaseTaskWithRetry,
    user_id: int,
) -> int:
    """Update user details. Returns user_id.

    In case the user is innaccessible, if it's a placeholder user, it will update the name to 'innaccessible' and return the user_id. otherwise, nothing will be done.
    """

    # superhosts flag is only avaible in listing details or search results.

    from ubdc_airbnb.workunits import (
        is_user_placeholder,
        update_user_details_from_airbnb_usr_response,
    )

    task_id = self.request.id
    user, created = AirBnBUser.objects.get_or_create(user_id=user_id)
    try:
        airbnb_response = AirBnBResponse.objects.fetch_response(
            user_id=user_id,
            type=AirBnBResponseTypes.userDetail,
            task_id=task_id,
        )
    except (HTTPError, ProxyError) as exc:
        logger.info(f"user_id: {user_id} is inaccessible", exc)
        if is_user_placeholder(user):
            user.first_name = "INACCESSIBLE"
            user.save()
        a = 1
        return user_id
    finally:
        user.responses.add(airbnb_response)

    update_user_details_from_airbnb_usr_response(user, airbnb_response)
    return user_id


@shared_task(bind=True)
def task_debug_wait(self, value, wait=0, verbose=True):
    """A debug/sample task that prints the value after {wait} seconds"""
    if verbose:
        logger.info("Request: {0!r}".format(self.request))
    if wait > 0:
        import time

        time.sleep(wait)

    return value


@shared_task
def task_debug_sometimes_fail(fail_percentage=0.8, verbose=True) -> str:
    if random() > 1 - fail_percentage:
        if verbose:
            logger.info("retrying")
        raise UBDCRetriableError(":)")
    return "Finished"


@shared_task
def task_tidy_grids(less_than: int = 50):
    less_than = int(less_than)
    if less_than < 0:
        raise ValueError("Error: less_than must be a positive integer")

    qk_sizes: dict = (
        UBDCGrid.objects.all().annotate(qk_len=Length("quadkey")).aggregate(max_qk=Max("qk_len"), min_qk=Min("qk_len"))
    )

    min_qk = qk_sizes["min_qk"]
    max_qk = qk_sizes["max_qk"]
    base_qs = UBDCGrid.objects.annotate(qk_len=Length("quadkey"))

    c = Counter()
    try:
        with transaction.atomic():
            # take care of overlaps
            logger.info("Removing Grids that overlap with their parent")
            for zoom in range(min_qk, max_qk + 1):
                parent_grids = base_qs.filter(qk_len=zoom)

                if parent_grids.exists:
                    logger.info(f"Processing level {zoom}")
                    for p_grid in parent_grids:
                        candidates = UBDCGrid.objects.filter(quadkey__startswith=p_grid.quadkey).exclude(
                            quadkey=p_grid.quadkey
                        )
                        candidates.delete()
                    c.update(("ovelaped",))

            logger.info(f"Merging grids with less than {less_than} listings")
            for zoom in range(max_qk, min_qk - 1, -1):
                logger.info(f"Processing level {zoom}")
                parent_grids = (
                    base_qs.filter(qk_len=zoom)
                    .annotate(p_qk=Substr("quadkey", 1, zoom - 1))
                    .values("p_qk")
                    .annotate(
                        p_qk_sum=Sum("estimated_listings"),
                        qk_children=Count("id"),
                        extent=Extent("geom_3857"),
                    )
                    .filter(p_qk_sum__lt=less_than)
                    .filter(qk_children=4)
                    .order_by("-p_qk_sum", "p_qk")
                )

                if parent_grids.exists():
                    for p_grid in parent_grids:
                        qk = p_grid["p_qk"]
                        bbox = GEOSPolygon.from_bbox(p_grid["extent"])
                        listings_count = AirBnBListing.objects.filter(geom_3857__intersects=bbox).count()
                        if listings_count > less_than:
                            logger.info(f"{qk} grid would contain {listings_count} known listings. Skipping")
                            c.update(("skipped",))
                            continue

                        estimated_listings = p_grid["p_qk_sum"]
                        UBDCGrid.objects.filter(quadkey__startswith=qk).delete()
                        g = UBDCGrid.objects.create_from_quadkey(quadkey=qk)
                        g.estimated_listings = estimated_listings
                        g.save()
                        c.update(("made",))
            tidied = c.get("made", 0) + c.get("ovelaped", 0)
            tidied_lbl = tidied if tidied else "No"

        logger.info(f"Command Finished. Tidied {tidied_lbl} tiles")

    except Exception as excp:
        logger.info(f"Transaction aborted.")
        raise excp


@shared_task(bind=True)
def task_debug_add_w_delay(self: Task, x: int, y: int):
    """A sample task, shows that everything works"""
    import time

    logger.info(f"Greetings from task {self.request.id}, using {type(self)} task")
    time.sleep(5)
    return x + y


__all__ = [
    "task_get_listing_details",
    "task_debug_add_w_delay",
    "task_debug_sometimes_fail",
    "task_debug_wait",
    "task_discover_listings_at_grid",
    "task_register_listings_or_divide_at_quadkey",
    "task_get_booking_detail",
    "task_get_or_create_user",
    "task_update_calendar",
    "task_update_or_add_reviews_at_listing",
    "task_update_user_details",
    "task_tidy_grids",
]
