from functools import partial
from json import JSONDecodeError
from typing import List, Union, Optional

import mercantile
import requests
from celery.utils.log import get_task_logger
from django.contrib.gis.geos.polygon import Polygon as GEOSPolygon
from django.db import models
from django.utils.timesince import timesince
from more_itertools import collapse
from requests import HTTPError
from requests.exceptions import ProxyError

from ubdc_airbnb import models as app_models
from ubdc_airbnb.airbnb_interface import airbnb_client
from ubdc_airbnb.convenience import reproject, make_point, postgis_distance_a_to_b, query_params_from_url
from ubdc_airbnb.errors import UBDCRetriableError, UBDCError
from ubdc_airbnb.utils.json_parsers import airbnb_response_parser

logger = get_task_logger(__name__)


class AirBnBResponseManager(models.Manager):

    def response_and_create(
            self, method_name: str,
            _type: str,
            task_id: str = None,
            **kwargs):

        method = getattr(airbnb_client, method_name)

        if method is None:
            raise Exception(f'{method_name} is not a valid method.')

        logger.info(f"method:{method.__name__} params:{kwargs}")
        try:
            response, payload = method(**kwargs)
        except (HTTPError, ProxyError) as exc:
            response = exc.response

        # if response is not None:
        listing_id = kwargs.get('listing_id', None)
        obj = self.create_from_response(
            response=response,
            _type=_type,
            task_id=task_id,
            listing_id=listing_id)
        try:
            response.raise_for_status()
        except (HTTPError, ProxyError) as exc:
            exc.ubdc_response = obj
            raise exc

        return obj

    def create_from_response(
            self, response: requests.Response,
            _type: str,
            task_id: str = None,
            listing_id: int = None):

        from ubdc_airbnb.models import UBDCTask
        if _type is None:
            # TODO: Heuristics?
            _type = None

        if _type not in ['USR', 'SHM', 'SRH'] and listing_id is None:
            raise AttributeError('Listing_id is not set for a request that should have one')

        try:
            payload = response.json()

        except JSONDecodeError as e:
            logger.info('Error when trying to decode the response payload: \n'
                        f'\tResponse status_code:{response.status_code} \n'
                        f'\tResponse Content: {response.content}. ')
            raise UBDCError(f'Response text was not Json. It was {response.text}') from e

        except AttributeError as e:
            # there are cases where the response come back Empty?.
            logger.info('Attribute error came back empty')
            raise UBDCRetriableError('Attribute error, retrying') from e

        ubdc_task = UBDCTask.objects.filter(task_id=task_id).first()  # returns None if not found

        params = {}
        params.update(
            _type=_type,
            listing_id=listing_id,
            status_code=response.status_code,
            request_headers=dict(**response.request.headers),
            payload=payload,
            url=response.url,
            query_params=query_params_from_url(response.url),
            seconds_to_complete=response.elapsed.seconds,
        )

        obj = self.create(ubdc_task=ubdc_task, **params)

        return obj


class AirBnBListingManager(models.Manager):

    def create_from_data(self, listing_id: int, lon: float, lat: float) -> 'app_models.AirBnBListing':
        """ Create an AirBnBListing Point from data. The returned object is saved in the Database
         :param listing_id:
         :param lon: Longitude in EPSG:4326
         :param lat: Latitude in EPSG:4326
         """

        # prev_location = app_models.AirBnBListing.objects.get(listing_id=listing_id).geom_3857
        _4326_point = make_point(lon, lat, 4326)
        _3857_point = reproject(_4326_point, to_srid=3857)
        obj = self.create(
            listing_id=listing_id,
            geom_3857=_3857_point
        )

        return obj

    def from_endpoint_explore_tabs(self, response: dict, save: bool = True) -> List['app_models.AirBnBListing']:
        """ TODO: DOC """
        if save:
            op = self.create
        else:
            op = self.model

        listings_objects = []
        sections = response['explore_tabs'][0]['sections']
        for section in sections:
            listings = section.get('listings', None)
            if listings is None:
                continue

            for listing in listings:
                listing_profile = listing['listing']
                listing_id = listing_profile.get('id')
                try:
                    u = self.get(listing_id=listing_id)
                except self.model.DoesNotExist:
                    obj = op(
                        listing_id=listing_id,
                        geom_3857=reproject(
                            make_point(x=listing_profile['lng'], y=listing_profile['lat'], srid=4326),
                            to_srid=3857))
                    listings_objects.append(obj)
                else:
                    print(
                        f'Listing with the airbnb_id {listing_id} was found in a previous iteration '
                        f'({timesince(u.timestamp)} ago)')

        return listings_objects


class UserManager(models.Manager):

    def create_from_response(self, ubdc_response: 'app_models.AirBnBResponse' = None,
                             user_id: int = None, ) -> 'app_models.AirBnBUser':
        """ Create an AirBnBUser from an airbnb response or a placeholder AirbnbUser from just hte user_id  """

        #  If airbnb_response = None, make DUMMY entry

        if user_id is None and ubdc_response is None:
            raise ValueError('Both user_id and airbnb_response are None')

        if ubdc_response.status_code > 299:
            payload = {}
            user_data = {}
        else:
            payload = ubdc_response.payload
            user_data = payload['user']

        # extract pics
        try:
            picture_url = airbnb_response_parser.profile_pics(payload)[0].split('?')[0]
        except IndexError:
            picture_url = ''
            print(f'!!! WARNING !!! Could not find a picture_url for {user_data.get("id", user_id)}')

        obj = self.create(
            user_id=user_data.get('id', user_id),
            first_name=user_data.get('first_name', 'UNKNOWN-DUMMY'),
            about=user_data.get('about', 'UNKNOWN-DUMMY'),
            airbnb_listing_count=user_data.get('listings_count', 0),
            verifications=user_data.get('verifications', []),
            picture_url=picture_url,
            created_at=user_data.get('created_at', None),
            location=user_data.get('location', 'UNKNOWN-DUMMY'),
        )
        obj.responses.add(ubdc_response)
        obj.save()

        return obj


class UBDCGridManager(models.Manager):

    # def get_queryset(self):
    #     """ Returns the default QS infused with "number_of_listings" annotation, """
    #
    #     qs = super().get_queryset()
    #     # Right, first we filter the Listings, by 'this' geometry, refered by the OuterRef,
    #     # then we annotate each row with a arbitrary lbl, to group by later.
    #     # then we Count by that lbl, and exporting just that value to make django happy.
    #     sub = app_models.AirBnBListing.objects.filter(geom_3857__within=OuterRef('geom_3857')). \
    #         annotate(lbl=Value('fukU', output_field=CharField())).values('lbl').order_by(). \
    #         annotate(c=Count('lbl')).values('c')
    #
    #     return qs.annotate(number_of_listings=Subquery(sub, output_field=CharField()))

    def has_quadkey(self, quadkey) -> bool:
        return self.filter(quadkey=quadkey).exists()

    def create_from_quadkey(self, quadkey: Union[str, mercantile.Tile], save=False,
                            allow_overlap_with_currents=True) -> 'app_models.UBDCGrid':

        # cast from tile->qk to facilitate the allow_overlap_with_currents
        # routine in  create_from_tile.
        # TODO:NOTE: bad practice, maybe refactor?
        if isinstance(quadkey, mercantile.Tile):
            quadkey = mercantile.quadkey(quadkey)

        tile = mercantile.quadkey_to_tile(quadkey)
        return self.create_from_tile(tile, allow_overlap_with_currents=allow_overlap_with_currents, save=save, )

    def create_from_tile(self,
                         tile: mercantile.Tile,
                         allow_overlap_with_currents: bool = False,
                         save: bool = False) -> \
            Union['app_models.UBDCGrid', List['app_models.UBDCGrid'], None]:
        """ Make an UBDCGrid entry and return a ref of it. """

        quadkey = mercantile.quadkey(tile)
        bbox = list(mercantile.xy_bounds(*tile))
        min_x, min_y, max_x, max_y = bbox
        mid_x = min_x + max_x / 2
        mid_y = min_y + max_y / 2

        if save:
            op = self.create
        else:
            op = self.model
        geom_3857 = GEOSPolygon.from_bbox(bbox)

        if not allow_overlap_with_currents:
            overlapping_grids = self.filter(quadkey__startswith=mercantile.quadkey(tile))
            if overlapping_grids.count() > 0:
                children = mercantile.children(tile)

                if self.has_quadkey(quadkey):
                    self.get(quadkey=quadkey).delete()

                children = filter(lambda x: not self.has_quadkey(mercantile.quadkey(x)), children)
                create_from_quadkey = partial(self.create_from_quadkey, save=save,
                                              allow_overlap_with_currents=allow_overlap_with_currents)
                res = list(map(create_from_quadkey, children))
                return list(collapse(res))

        ubdcgrid = op(
            geom_3857=geom_3857,
            quadkey=quadkey,
            bbox_ll_ur=','.join(map(str, bbox)),
            tile_x=tile.x,
            tile_y=tile.y,
            tile_z=tile.z,
            area=geom_3857.area,
            x_distance_m=postgis_distance_a_to_b((min_x, mid_y), (max_x, mid_y)),
            y_distance_m=postgis_distance_a_to_b((mid_x, min_y), (mid_x, max_y))
        )

        return ubdcgrid
