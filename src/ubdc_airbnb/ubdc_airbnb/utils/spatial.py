import warnings
from collections import abc
from typing import TYPE_CHECKING, Annotated, Dict, Literal, Sequence, Union

from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.geos import MultiLineString as GEOSMultiLineString
from django.contrib.gis.geos import MultiPolygon as GEOSMultiPolygon
from django.contrib.gis.geos import Point as GEOSPoint
from django.db import connection
from django.db.models import Aggregate, Subquery
from jsonpath_ng import parse
from more_itertools import sliced


class ST_Union(Aggregate):
    name = "st_union"
    function = "ST_UNION"
    allow_distinct = False
    arity = 1


def get_world_cross() -> GEOSMultiLineString:
    prime_meridian = GEOSGeometry("LINESTRING(0 -90, 0 90)", srid=4326)
    prime_parallel = GEOSGeometry("LINESTRING(-180 0, 180 0)", srid=4326)

    cross: GEOSMultiLineString = prime_meridian.union(prime_parallel)
    cross.srid = 4326
    return cross


def geom_intersects_world_cross(geom: GEOSGeometry) -> bool:
    """Checks if a geometry intersects with the prime meridian or prime parallel."""
    cross = get_world_cross()
    if cross.srid != geom.srid:
        warnings.warn("Cross geometry has different SRID than the input geometry. Result may be incorrect.")
    return geom.intersects(cross)


def cut_polygon_at_prime_lines(polygon: GEOSGeometry) -> list[GEOSGeometry]:
    """Cut a polygon like geometry at the prime meridian or prime parallel and and returns a list of geometries."""
    # TODO: #10 develop this function and add tests

    assert polygon.srid == 4326, "This function only works with WGS84 geometries"

    cross = get_world_cross()

    if polygon.geom_type.startswith("GEOMETRYCOLLECTION"):
        rv = [cut_polygon_at_prime_lines(geom) for geom in polygon]
        from itertools import chain

        return chain(rv)

    if not polygon.intersects(cross):
        return [polygon]

    # delegeting this to the database, as there's no easy way to do this with
    # provided geos binding django offeres
    localised_cross = cross.intersection(polygon)
    polygon_wkt = polygon.ewkt
    cross_wkt = localised_cross.ewkt

    gc: GEOSGeometry | None = None
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
                WITH
                qq AS (
                        SELECT st_geomfromewkt(%s) blade),
                pp    AS (
                        SELECT st_geomfromewkt(%s) geom
                        )
                SELECT ST_AsEWKT(st_split(geom, blade))
                FROM
                    qq, pp;""",
            [cross_wkt, polygon_wkt],
        )

        row = cursor.fetchone()
        wkt: str = row[0]
        gc = GEOSGeometry.from_ewkt(wkt)
        assert gc is not None

    rv = list(gc)
    return rv


def get_quadkeys_of_aoi(aoi_pk: int) -> list[str]:
    """Returns a list of database quadkeys that intersect with given AOI-key"""
    from ubdc_airbnb.models import AOIShape, UBDCGrid

    aoi = AOIShape.objects.get(pk=aoi_pk)
    qs_grids = (
        UBDCGrid.objects.filter(geom_3857__intersects=aoi.geom_3857)
        .order_by("quadkey")
        .values("quadkey")
        .distinct("quadkey")
    )

    return [grid["quadkey"] for grid in qs_grids]


def get_quadkeys_for(
    purpose: Literal["discover_listings"],
) -> list[str]:
    # TODO: #7 Create case test for this.
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
        .distinct("quadkey")
        .values_list("quadkey", flat=True)
    )

    return list(qs_grids)


def listing_locations_from_response(response: dict) -> Dict[str, GEOSPoint]:
    """Returns a dict with all the listings_ids and points found in this parsed response.
    :type response: dict

    """
    result: Dict[str, GEOSPoint] = {}

    for pattern in [r"$..listing[id_str,lat,lng]"]:
        parser = parse(pattern)
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


def distance_a_to_b(point_a, point_b, srid=3857):
    # TODO: #8 Develop this stub function and add tests.
    raise NotImplementedError("This function is a stub. Use postgis_distance_a_to_b instead.")


def postgis_distance_a_to_b(
    point_a: Union[str, GEOSPoint, Annotated[Sequence[float], 2]],
    point_b: Union[str, GEOSPoint, Annotated[Sequence[float], 2]],
    srid=3857,
):
    """Returns the distance between two points in meters.
    Function is a wrapper around the PostGIS ST_DISTANCE function."""
    # TODO: #11 Fix types and add tests

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


def reproject(
    geom: GEOSGeometry,
    to_srid: int = 3857,
    from_srid: int | None = None,
) -> GEOSGeometry:
    from ubdc_airbnb.errors import UBDCCoordinateError

    """Reprojects to new SRID (default epsg=3857). Returns new geometry."""
    # TODO: #9 Add test

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
