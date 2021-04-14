from collections import Iterable, Counter
from typing import List, Optional, Tuple

import mercantile
from django.contrib.gis.db.models import Extent
from django.contrib.gis.geos import Polygon as GEOSPolygon
from django.db import transaction
from django.db.models import Max, Min, Count, Sum
from django.db.models.functions import Length, Substr
from requests import Response

from app import ubdc_airbnbapi
from app.errors import UBDCError
from app.models import UBDCGrid, AirBnBListing


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

    west = log_lat_bbox.west
    south = log_lat_bbox.south
    east = log_lat_bbox.east
    north = log_lat_bbox.north

    number_of_listings = ubdc_airbnbapi.number_of_listings(west=west, south=south, east=east, north=north)
    response = ubdc_airbnbapi.response

    return number_of_listings, response


def tidy_grids(less_than: int = 50):
    iless_than = int(less_than)
    if iless_than < 0:
        raise ValueError('Error: less_than must be a positive integer')

    qk_sizes: dict = UBDCGrid.objects.all().annotate(qk_len=Length('quadkey')).aggregate(max_qk=Max('qk_len'),
                                                                                         min_qk=Min('qk_len'))

    min_qk = qk_sizes['min_qk']
    max_qk = qk_sizes['max_qk']
    base_qs = UBDCGrid.objects.annotate(qk_len=Length('quadkey'))

    c = Counter()
    try:
        with transaction.atomic():
            # take care of overlaps
            print('Removing Grids that overlap with their parent')
            for zoom in range(min_qk, max_qk + 1):
                parent_grids = base_qs.filter(qk_len=zoom)

                if parent_grids.exists:
                    print(f"Processing level {zoom}")
                    for p_grid in parent_grids:
                        candidates = UBDCGrid.objects.filter(quadkey__startswith=p_grid.quadkey).exclude(
                            quadkey=p_grid.quadkey)
                        candidates.delete()
                    c.update(('ovelaped',))

            print(f'Merging grids with less than {iless_than} listings')
            for zoom in range(max_qk, min_qk - 1, -1):
                print(f"Processing level {zoom}")
                parent_grids = (base_qs.filter(qk_len=zoom)
                                .annotate(p_qk=Substr('quadkey', 1, zoom - 1))
                                .values('p_qk')
                                .annotate(
                    p_qk_sum=Sum('estimated_listings'),
                    qk_children=Count('id'),
                    extent=Extent('geom_3857')
                )
                                .filter(p_qk_sum__lt=iless_than)
                                .filter(qk_children=4)
                                .order_by('-p_qk_sum', 'p_qk'))

                if parent_grids.exists():
                    for p_grid in parent_grids:
                        qk = p_grid['p_qk']
                        bbox = GEOSPolygon.from_bbox(p_grid['extent'])
                        listings_count = AirBnBListing.objects.filter(geom_3857__intersects=bbox).count()
                        if listings_count > iless_than:
                            print(f"{qk} grid would contain {listings_count} known listings. Skipping ")
                            c.update(('skipped',))
                            continue

                        estimated_listings = p_grid['p_qk_sum']
                        UBDCGrid.objects.filter(quadkey__startswith=qk).delete()
                        g = UBDCGrid.objects.create_from_quadkey(quadkey=qk)
                        g.estimated_listings = estimated_listings
                        g.save()
                        c.update(('made',))
            tidied = c.get("made", 0) + c.get("ovelaped", 0)
            tidied_lbl = tidied if tidied else "No"

        print(f'Command Finished. Tidied {tidied_lbl} tiles')

    except Exception as excp:
        # self.stdout.write(self.style.ERROR(f'An error has occured. Db was reverted back to its original state'))
        raise excp
