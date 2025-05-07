from random import random
from typing import TYPE_CHECKING, Any, Optional, Union

from celery import Task, group, shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.utils import timezone

from ubdc_airbnb import model_defaults
from ubdc_airbnb.airbnb_interface.airbnb_api import AirbnbApi
from ubdc_airbnb.errors import UBDCRetriableError
from ubdc_airbnb.models import (
    AirBnBListing,
    AirBnBResponse,
    AirBnBResponseTypes,
    AirBnBReview,
    AirBnBUser,
    UBDCGrid,
    UBDCGroupTask,
)
from ubdc_airbnb.task_managers import BaseTaskWithRetry
from ubdc_airbnb.utils.grids import bbox_from_quadkey

logger = get_task_logger(__name__)
airbnb_client = AirbnbApi(proxy=settings.AIRBNB_PROXY)


if TYPE_CHECKING:
    from celery.result import GroupResult


@shared_task(bind=True)
def task_add_reviews_of_listing(
    self: Task,
    listing_id: int,
    offset=0,
    limit=100,
    **kwargs,
) -> None:
    """
    Fetches review responses. Adds any new users in the process.
    """

    task_id = self.request.id
    listing = AirBnBListing.objects.get(listing_id=listing_id)

    response_review = AirBnBResponse.objects.fetch_response(
        offset=offset,
        limit=limit,
        type=AirBnBResponseTypes.review,
        listing_id=listing_id,
        task_id=task_id,
    )

    payload = response_review.payload
    reviews_count = payload["metadata"]["reviews_count"]
    pages = reviews_count // limit
    current_offset = int(response_review.query_params["_offset"])
    has_multiple_pages = pages > 1
    current_page = current_offset // limit  # 0 based page

    if has_multiple_pages and current_page == 0:
        # submit the other pages
        for page in range(1, pages + 1):
            listing_id = listing_id
            task = task_add_reviews_of_listing.s(
                listing_id=listing_id,
                offset=page * limit,
                limit=limit,
            )
            task.apply_async()
        listing.reviews_updated_at = timezone.now()
        listing.save()

    # process the review payload
    reviews: list[dict[str, Any]] = payload["reviews"]
    for review in reviews:
        review_id = review["id"]
        author_data = review["author"]
        recipient_data = review["recipient"]
        author, _ = AirBnBUser.objects.get_or_create(user_id=author_data["id"])
        recipient, _ = AirBnBUser.objects.get_or_create(user_id=recipient_data["id"])
        listing.users.add(author, recipient)

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


@shared_task(bind=True, acks_late=True)  # type: ignore
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
    ubdc_response = AirBnBResponse.objects.fetch_response(
        type=AirBnBResponseTypes.calendar,
        calendar_months=months,
        task_id=self.request.id,
        asset_id=listing_id,
    )

    listing_entry.responses.add(ubdc_response)
    listing_entry.calendar_updated_at = timezone.now()
    listing_entry.save()

    return listing_entry.listing_id


@shared_task(bind=True)
def task_get_booking_detail(self: Task, listing_id: int) -> int:
    """
    Get a booking detail for this listing_id using the latest calendar from the database.
    Returns the listing_id if operation was successful.
    """

    listing, created = AirBnBListing.objects.get_or_create(listing_id=listing_id)
    calendar: AirBnBResponse = (
        AirBnBResponse.objects.filter(listing_id=listing_id, _type=AirBnBResponseTypes.calendar)
        .order_by("timestamp")
        .first()
    )  # type: ignore

    booking_response = AirBnBResponse.objects.fetch_response(
        listing_id=listing_id,
        calendar=calendar.payload,
        type=AirBnBResponseTypes.bookingQuote,
        task_id=self.request.id,
    )
    listing.responses.add(booking_response)

    listing.booking_quote_updated_at = timezone.now()
    listing.save()

    logger.info(f"BookingQuote:LISTING_ID:{listing_id}:SUCCESS")
    return listing.listing_id


@shared_task(bind=True)
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

    airbnb_response: AirBnBResponse = AirBnBResponse.objects.fetch_response(
        asset_id=listing_id_int,
        task_id=task_id,
        type=AirBnBResponseTypes.listingDetail,
    )
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


@shared_task(bind=True)  # type: ignore
def task_get_next_page_homes(self: BaseTaskWithRetry, parent_page_task_id: str):
    "Uses meta from the parent task to get the next page of listings."
    from ubdc_airbnb.utils.json_parsers import airbnb_response_parser
    from ubdc_airbnb.workunits import (
        get_next_page_payload,
        register_listings_from_response,
    )

    logger.info(f"Task {parent_page_task_id} is getting the next page of listings.")
    logger.info(f"Task {self.request.id} is getting the next page of listings.")

    this_task_id = self.request.id
    assert this_task_id is not None
    payload: dict = get_next_page_payload(parent_page_task_id=parent_page_task_id, this_task_id=this_task_id)

    # process this page results
    register_listings_from_response(payload)

    has_next_page = airbnb_response_parser.has_next_page(payload)
    if has_next_page:
        # shoot another task/request

        # self is the new parent task
        next_page_task = task_get_next_page_homes.s(parent_page_task_id=self.request.id)
        next_page_task.apply_async()


@shared_task(bind=True)  # type: ignore
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

    # check bbox and if it's paginated, divide and resubmit
    # corner case:
    # if the grid is too deep to divide,
    # following the pages.

    from ubdc_airbnb.utils.grids import replace_quadkey_with_children
    from ubdc_airbnb.utils.json_parsers import airbnb_response_parser
    from ubdc_airbnb.workunits import (
        bbox_has_next_page,
        register_listings_from_response,
    )

    task_id = self.request.id
    grid: UBDCGrid = UBDCGrid.objects.get(quadkey=quadkey)
    lnglat_bbox = bbox_from_quadkey(grid.quadkey)
    bbox = lnglat_bbox._asdict()

    response_pk, has_next_page = bbox_has_next_page(task_id=task_id, **bbox)
    response: AirBnBResponse = AirBnBResponse.objects.get(pk=response_pk)
    payload = response.payload
    listings = register_listings_from_response(payload)

    grid.datetime_last_estimated_listings_scan = timezone.now()

    logger.info(f"Grid {grid.quadkey} has next page: {has_next_page}")

    if has_next_page and len(quadkey) >= settings.MAX_GRID_LEVEL:
        # Safeguard; we don't want to divide too much.
        # We could find ourself here as a result of a broken SHR response.
        # default is 22 but can be configured in settings.
        # 22 represents a ~10m x 10m grid

        logger.info(f"Quadkey {quadkey} is too deep to divide. (max: {settings.MAX_GRID_LEVEL}. This: {len(quadkey)}).")
        job = task_get_next_page_homes.s(parent_page_task_id=task_id)
        job.apply_async()

    if has_next_page and len(quadkey) < settings.MAX_GRID_LEVEL:
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

    estimated_listings = airbnb_response_parser.listing_count(response=payload)
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


@shared_task(bind=True)  # type: ignore
def task_update_user_details(
    self: BaseTaskWithRetry,
    user_id: int,
) -> int:
    """Update user details. Returns user_id."""

    task_id = self.request.id
    user, _ = AirBnBUser.objects.get_or_create(user_id=user_id)
    airbnb_response = AirBnBResponse.objects.fetch_response(
        user_id=user_id,
        type=AirBnBResponseTypes.userDetail,
        task_id=task_id,
    )
    if user.is_placeholder:
        user.first_name = model_defaults.AIRBNBUSER_DISABLED
        user.save()

    if airbnb_response.is_user_valid:
        user.update_from_response(airbnb_response)

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


@shared_task(bind=True)
def task_debug_add_w_delay(self: Task, x: int, y: int):
    """A sample task, shows that everything works"""
    import time

    logger.info(f"Greetings from task {self.request.id}, using {type(self)} task")
    time.sleep(5)
    return x + y


__all__ = [
    # Data Fetching tasks
    "task_get_listing_details",
    "task_update_calendar",
    "task_update_user_details",
    "task_get_booking_detail",
    "task_add_reviews_of_listing",
    # Discovery tasks
    "task_register_listings_or_divide_at_quadkey",
    "task_get_next_page_homes",
    # debug tasks
    "task_debug_sometimes_fail",
    "task_debug_add_w_delay",
    "task_debug_wait",
]
