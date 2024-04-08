from typing import Iterable, List, Optional

import mercantile
from django.contrib.gis.geos import GEOSGeometry

from ubdc_airbnb.errors import UBDCError


def generate_initial_grid(
    aoishape_id: int,
    profile: str = "rural",
    zoom: Optional[int] = None,
) -> List[str]:
    """Generates an initial grid for a the aoishape (identified by it's ID) based either in a proposed
    zoom level or profile.
    These grids should be then further refined using the estimated_listings_or_divide
    """
    from ubdc_airbnb.models import AOIShape, UBDCGrid

    if not zoom and not profile:
        raise UBDCError("Either zoom or profile must be specified.")

    if not zoom:
        # higher, means finer scale (MORE zoom, 0 -> whole world)
        if profile.lower() == "urban":
            zoom = 15
        elif profile.lower() == "rural":
            zoom = 12
        else:
            raise UBDCError("The profile given is not valid. Must be either urban or rural")
    # zoom = zoom

    try:
        aoi_shape = AOIShape.objects.get(pk=aoishape_id)
    except AOIShape.DoesNotExist:
        raise UBDCError('Shape "%s" does not exist.' % aoishape_id)

    init_grid = UBDCGrid.objects.create_from_tile(aoi_shape.as_mtile(), allow_overlap_with_currents=True)

    children = init_grid.children(intersect_with=aoi_shape.id, zoom=zoom)

    # TODO: replace with more_itertools.collapse
    def flatten(maybe_a_list_like):
        for element in maybe_a_list_like:
            if isinstance(element, Iterable) and not isinstance(element, (str, bytes)):
                yield from flatten(element)
            else:
                yield element

    grid_bag: List[UBDCGrid] = []
    for child in children:
        grids = flatten([UBDCGrid.objects.create_from_tile(child)])
        #         could generate sublist  ----^, replace with more_itertools.collapse
        for grid in grids:
            if UBDCGrid.objects.filter(quadkey=grid.quadkey):
                print(f"{grid} already exists in the database. Skipping")
                continue

            grid_bag.append(grid)

    UBDCGrid.objects.bulk_create(grid_bag)
    print(f"Command ran successfully: Generated %s UBDC tiles" % len(grid_bag))

    return [grid.quadkey for grid in grid_bag]


def bbox_from_quadkey(qk: str) -> mercantile.LngLatBbox:
    """
    :param qk: quadkey
    :type qk: str
    :return: numbers of estimated listings in this bbox
    :rtype: int, Response
    """
    tile = mercantile.quadkey_to_tile(qk=qk)
    bbox = mercantile.bounds(tile)

    return bbox


def grids_from_qk(quadkey: str) -> list[str]:
    from itertools import chain

    from ubdc_airbnb.models import UBDCGrid

    # check if the quadkey has any parents. If it does, return None
    if qk_has_parent(quadkey):
        return []

    if qk_has_children(quadkey):
        tile = mercantile.quadkey_to_tile(qk=quadkey)
        tiles = mercantile.children(tile)
        qks = [mercantile.quadkey(tile) for tile in tiles]
        rv = [x for x in [grids_from_qk(qk) for qk in qks] if x is not None]

        return list(chain.from_iterable(rv))

    return [
        quadkey,
    ]


def qk_has_children(quadkey: str) -> bool:
    """query if a quadkey has children in the database"""
    from django.db.models import Q

    from ubdc_airbnb.models import UBDCGrid

    q = Q(quadkey=quadkey) | Q(quadkey__startswith=quadkey)

    return UBDCGrid.objects.filter(q).exists()


def qk_has_parent(quadkey: str) -> bool:
    "query if a quadkey has a parent in the database"
    from django.db.models import Q

    from ubdc_airbnb.models import UBDCGrid

    assert len(quadkey) > 1, "Quadkey must be at least 2 characters long"

    q = Q(quadkey=quadkey)
    while quadkey:
        q = q | Q(quadkey=quadkey)
        quadkey = quadkey[:-1]

    return UBDCGrid.objects.filter(q).exists()


def quadkeys_of_geom(geom: GEOSGeometry) -> list[str]:
    "Returns a list of quadkeys that intersect with an areal geometry"

    # has geometry area?
    # trick to filter non-empty geometries
    if not geom.area:
        raise UBDCError("Geometry has no area")

    if geom.geom_type.startswith("MULTI"):
        geometries = [g for g in geom]
    else:
        geometries = [geom]

    bboxes = [g.extent for g in geometries]
    qks = [mercantile.bounding_tile(*extent) for extent in bboxes]

    return [mercantile.quadkey(tile) for tile in qks]
