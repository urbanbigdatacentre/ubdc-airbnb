from typing import Iterable, List, Optional, Set

import mercantile
from django.contrib.gis.geos import GEOSGeometry

from ubdc_airbnb.errors import UBDCError


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


def _clean_qk(quadkey: str) -> list[str]:
    from itertools import chain

    # check if the quadkey has any parents. If it has that means that is overlaped by an existing qk.
    # return None in this case
    if qk_has_parent(quadkey):
        return []

    if qk_has_children(quadkey):
        tile = mercantile.quadkey_to_tile(qk=quadkey)
        tiles = mercantile.children(tile)
        qks = [mercantile.quadkey(tile) for tile in tiles]
        rv = [x for x in [clean_quadkeys(qk) for qk in qks] if x is not None]

        return list(chain.from_iterable(rv))

    return [quadkey]


def clean_quadkeys(quadkey: str | list[str]) -> list[str]:
    "Given a string or list of stings representing quadkeys, returns a list of unique quadkeys that can be added in the database."
    from itertools import chain

    if isinstance(quadkey, str):
        quadkey = [
            quadkey,
        ]

    rv: Set[str] = set()
    for qk in quadkey:
        qks = _clean_qk(qk)
        if qks is None:
            continue
        qks = list(chain(qks))
        rv.update(qks)

    return list(rv)


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


def replace_quadkey_with_children(qk: str) -> List[str]:
    "Replaces the given grid with the specified qk with its children. The function uses an atomoc transaction. Returns the new quadkeys."
    from django.db import transaction

    from ubdc_airbnb.models import UBDCGrid

    with transaction.atomic():
        parent_grid = UBDCGrid.objects.get(quadkey=qk)
        children = parent_grid.children()
        parent_grid.delete()
        UBDCGrid.objects.bulk_create(children)
        return [c.quadkey for c in children]
