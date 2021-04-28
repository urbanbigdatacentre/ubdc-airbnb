from collections import Iterable
from typing import List, Optional

import mercantile
from app.errors import UBDCError


def generate_initial_grid(aoishape_id: int, profile: Optional[str] = 'rural', zoom: Optional[int] = None):
    """ Generates an initial grid for a the aoishape (identified by it's ID) based either in a proposed
     zoom level or profile.
     These grids should be then further refined using the estimated_listings_or_divide
     """
    from app.models import AOIShape, UBDCGrid

    if not zoom and not profile:
        raise UBDCError('Either zoom or profile must be specified.')

    if not zoom:
        # higher, means finer scale (MORE zoom, 0 -> whole world)
        if profile.lower() == 'urban':
            zoom = 15
        elif profile.lower() == 'rural':
            zoom = 12
        else:
            raise UBDCError('The profile given is not valid. Must be either urban or rural')
    # zoom = zoom

    try:
        aoi_shape = AOIShape.objects.get(pk=aoishape_id)
    except AOIShape.DoesNotExist:
        raise UBDCError('Shape "%s" does not exist.' % aoishape_id)

    init_grid = UBDCGrid.objects.create_from_tile(aoi_shape.as_mtile(),
                                                  allow_overlap_with_currents=True)

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
                print(f'{grid} already exists in the database. Skipping')
                continue

            grid_bag.append(grid)

    UBDCGrid.objects.bulk_create(grid_bag)
    print(f'Command ran successfully: Generated %s UBDC tiles' % len(grid_bag))

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
