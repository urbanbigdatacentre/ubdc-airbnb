import warnings
from collections import abc
from typing import TYPE_CHECKING, Annotated, Dict, Literal, Sequence, Union

from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.geos import Point as GEOSPoint
from django.db import connection
from django.db.models import Aggregate, Subquery
from jsonpath_ng import parse
from more_itertools import sliced

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from ubdc_airbnb.models import AirBnBListing, UBDCGrid


class ST_Union(Aggregate):
    name = "st_union"
    function = "ST_UNION"
    allow_distinct = False
    arity = 1


def get_grids_for(
    purpose: Literal["discover_listings"],
) -> "QuerySet[UBDCGrid]":
    from ubdc_airbnb.models import AOIShape, UBDCGrid

    match purpose:
        case "discover_listings":
            list_aoi = AOIShape.objects.filter(collect_listing_details=True).values("collect_listing_details")
        case _:
            raise NotImplementedError()

    aoi_area_union = list_aoi.annotate(union=ST_Union("geom_3857"))
    qs_grids = (
        UBDCGrid.objects.filter(geom_3857__intersects=Subquery(aoi_area_union.values("union")))
        .order_by("quadkey")
        .values("quadkey")
    )

    return qs_grids.distinct("quadkey")


def get_listings_qs_for_aoi(purpose: Literal["calendar", "reviews", "listing_details"]) -> 'QuerySet["AirBnBListing"]':
    """Returns a QS with all the listings ids within an enabled AOI"""

    from ubdc_airbnb.models import AirBnBListing, AOIShape

    match purpose:
        case "listing_details":
            list_aoi = AOIShape.objects.filter(collect_listing_details=True).values("collect_listing_details")
        case "calendar":
            list_aoi = AOIShape.objects.filter(collect_calendars=True).values("collect_calendars")
        case "reviews":
            list_aoi = AOIShape.objects.filter(collect_reviews=True).values("collect_reviews")
        case _:
            raise ValueError("invalid argument")

    aoi_area_union = list_aoi.annotate(union=ST_Union("geom_3857"))
    qs_listings = AirBnBListing.objects.filter(geom_3857__intersects=Subquery(aoi_area_union.values("union")))

    qs_listings = qs_listings.order_by("listing_id").distinct("listing_id")

    return qs_listings


def listing_locations_from_response(response: dict) -> Dict[str, GEOSPoint]:
    """Returns a dict with all the listings_ids and points found in this parsed response.
    :type response: dict

    """
    result: Dict[str, GEOSPoint] = {}

    for p_string in [r"$..listing[id,lat,lng]", r"$..pdp_listing_detail[id,lat,lng]"]:
        parser = parse(p_string)
        hits = [m.value for m in parser.find(response)]
        if len(hits):
            _id: str
            lat: float
            lon: float
            for _id, lat, lon in sliced(hits, 3, strict=True):
                point = GEOSPoint(lon, lat, srid=4326)
                result[_id] = point
            return result
    return result


def postgis_distance_a_to_b(
    point_a: Union[str, GEOSPoint, Annotated[Sequence[float], 2]],
    point_b: Union[str, GEOSPoint, Annotated[Sequence[float], 2]],
    srid=3857,
):
    """TODO: DOC"""
    if isinstance(point_a, abc.Sequence) and not isinstance(point_a, str):
        point_a = GEOSPoint(*point_a)
    if isinstance(point_b, abc.Sequence) and not isinstance(point_b, str):
        point_b = GEOSPoint(*point_b)

    if not issubclass(type(point_a), GEOSGeometry):
        point_a = GEOSGeometry(point_a)
    if not issubclass(type(point_b), GEOSGeometry):
        point_b = GEOSGeometry(point_b)

    if point_b.geom_type != "Point" or point_a.geom_type != "Point":
        raise ValueError("This function works only with Point inputs")

    if point_a.srid is None:
        point_a.srid = srid
    if point_b.srid is None:
        point_b.srid = srid

    if point_a.srid != point_b.srid:
        raise ValueError("The input points have different SRIDs")

    with connection.cursor() as c:
        c.execute(
            f"""
            SELECT ST_DISTANCE(ST_GeomFromEWKT('{point_a.ewkt}'), ST_GeomFromEWKT('{point_b.ewkt}'))
        """
        )
        result = c.fetchone()[0]
        return float(result)


def make_point(x: float, y: float, srid: int = 4326) -> GEOSPoint:
    """Cast coordinates to Point object"""

    return GEOSPoint(x, y, srid=srid)


def reproject(geom: GEOSGeometry, to_srid: int = 3857, from_srid: int = None) -> GEOSGeometry:
    from ubdc_airbnb.errors import UBDCCoordinateError

    """ReProjects to new SRID (default epsg=3857). Returns new geometry."""
    if not issubclass(type(geom), GEOSGeometry):
        try:
            geom = GEOSGeometry(geom.ewkt)
        except:
            geom = GEOSGeometry(geom.wkt)

    if geom.srid is None and from_srid is None:
        raise UBDCCoordinateError("Source Coordinate System was not specified nor was embedded.")

    if geom.srid is None:
        geom.srid = 4326

    if geom.srid and from_srid:
        warnings.warn(f"Warning: Overriding the natural srid {geom.srid} with {from_srid}")
        geom.srid = from_srid

    return geom.transform(to_srid, clone=True)
