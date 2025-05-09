# units of work for the airbnb project.
# They normally would require db access to operate.

from celery.utils.log import get_task_logger
from django.contrib.gis.geos import GEOSGeometry
from django.utils import timezone

from ubdc_airbnb.models import AirBnBListing, AirBnBResponse, AirBnBResponseTypes
from ubdc_airbnb.utils.json_parsers import airbnb_response_parser

logger = get_task_logger(__name__)


def get_next_page_payload(parent_page_task_id: str, this_task_id: str) -> dict:

    obj: AirBnBResponse = AirBnBResponse.objects.get(ubdc_task_id=parent_page_task_id)
    logger.info(f"Parent Task ID: {parent_page_task_id}/found")
    response = obj.payload

    lnglat_bbox = airbnb_response_parser.get_lnglat_bbox(response=response)
    federated_search_session_id = airbnb_response_parser.get_federated_search_session_id(response=response)
    next_page_offset = airbnb_response_parser.get_next_page_offset(response=response)
    try:
        previous_page_offset = airbnb_response_parser.get_previous_page_items_offset(response=response)
    except AssertionError:
        # no previous page offset means we are at the first page
        previous_page_offset = 0
        items_per_grid = int(next_page_offset)
    else:
        items_per_grid = int((next_page_offset - previous_page_offset) / 2)

    # this needs to be an int. if float you'll get a 400 from the API
    # TODO: push validation to the api client

    logger.info(f"Next Page Offset: {next_page_offset}")
    logger.info(f"Previous Page Offset: {previous_page_offset}")
    logger.info(f"Items per grid: {items_per_grid}")

    bbox = lnglat_bbox._asdict()

    ubdc_response: AirBnBResponse = AirBnBResponse.objects.fetch_response(
        type=AirBnBResponseTypes.search,
        task_id=this_task_id,
        federated_search_session_id=federated_search_session_id,
        items_offset=next_page_offset,
        items_per_grid=items_per_grid,
        **bbox,
    )
    rv: dict = ubdc_response.payload

    return rv


def qk_has_next_page(quadkey: str, task_id=None) -> tuple[int, bool]:
    from ubdc_airbnb.models import UBDCGrid
    from ubdc_airbnb.utils.grids import bbox_from_quadkey

    grid: UBDCGrid = UBDCGrid.objects.get(quadkey=quadkey)
    bbox = bbox_from_quadkey(grid.quadkey)

    east = bbox.east
    north = bbox.north
    south = bbox.south
    west = bbox.west

    return bbox_has_next_page(east, north, south, west, task_id)


def bbox_has_next_page(
    east: float,
    north: float,
    south: float,
    west: float,
    task_id=None,
) -> tuple[int, bool]:
    """Queries the airbnb API and returns the pk of the response and a bool if the bbox has more pages."""

    ubdc_response: AirBnBResponse = AirBnBResponse.objects.fetch_response(
        type=AirBnBResponseTypes.search,
        task_id=task_id,
        west=west,
        east=east,
        south=south,
        north=north,
    )
    pk: int = ubdc_response.pk
    return pk, airbnb_response_parser.has_next_page(ubdc_response.payload)


def bbox_estimated_listings(
    east: float,
    north: float,
    south: float,
    west: float,
    task_id=None,
) -> int:
    """Return the estimated number of listings in the bbox. Tries to figure out if the number is correct or not, which if it's not it will return 0.

    The function will store the response in the database.
    """

    ubdc_response: AirBnBResponse = AirBnBResponse.objects.fetch_response(
        type=AirBnBResponseTypes.searchMetaOnly,
        task_id=task_id,
        west=west,
        east=east,
        south=south,
        north=north,
    )

    # grab the estimated listings
    estimated_listings = airbnb_response_parser.listing_count(ubdc_response.payload)
    # and the price histogram sum
    price_histogram_sum = airbnb_response_parser.price_histogram_sum(ubdc_response.payload)

    # I think i've seen cases where the estimated listings is >0,  but the price_histogram_sum is 0.
    # In this case, the metadata is are not correct.
    if price_histogram_sum > 0:
        return estimated_listings
    # otherwise, return 0
    return 0


def register_listings_from_response(response: dict) -> list[AirBnBListing]:
    "Extract the listing_ids from the response and register it to the model. Returns a list with references to listings."
    from collections import Counter

    from django.conf import settings

    from ubdc_airbnb.utils.spatial import listing_locations_from_response

    c = Counter()

    listings = listing_locations_from_response(response)
    rv: list[AirBnBListing] = []

    def significally_moved(listing, point) -> bool:
        delta_distance = listing.geom_3857.distance(point)
        move_threshold: str = settings.AIRBNB_LISTINGS_MOVED_MIN_DISTANCE
        rv = float(delta_distance) > float(move_threshold)
        # logger.info(f"{delta_distance} > {move_threshold} = {rv}")
        return rv

    for listing_id, point in listings.items():
        listing, created = AirBnBListing.objects.get_or_create(listing_id=listing_id)
        point_3857 = GEOSGeometry(point, srid=4326).transform(3857, clone=True)

        if created:
            listing.geom_3857 = point_3857
            c["created"] += 1
        else:
            # listing alreay exists, check if the geom is different
            if significally_moved(listing, point_3857):
                logger.info(f"Listing {listing_id} has significally moved.")
                c["existing"] += 1
                delta_distance = listing.geom_3857.distance(point_3857)
                listing.geom_3857 = point_3857
                key = timezone.now().isoformat()
                notes: dict = listing.notes
                notes[key] = {"from": listing.geom_3857.wkt, "to": point_3857.wkt, "distance": delta_distance}

        listing.save()
    logger.info(f"Created {c['created']} listings, updated {c['existing']} listings.")
    return rv
