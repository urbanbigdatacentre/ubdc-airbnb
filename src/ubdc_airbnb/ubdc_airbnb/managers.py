from json import JSONDecodeError
from typing import TYPE_CHECKING, Any, List, Literal, MutableMapping, Type

import mercantile
from celery.utils.log import get_task_logger
from django.conf import settings
from django.contrib.gis.geos.polygon import Polygon as GEOSPolygon
from django.db import models
from django.db.models import QuerySet, Subquery
from django.utils.timesince import timesince
from requests import HTTPError
from requests.exceptions import ProxyError

from ubdc_airbnb.convenience import query_params_from_url
from ubdc_airbnb.errors import UBDCError, UBDCRetriableError
from ubdc_airbnb.utils.json_parsers import airbnb_response_parser
from ubdc_airbnb.utils.spatial import (
    ST_Union,
    make_point,
    postgis_distance_a_to_b,
    reproject,
)

logger = get_task_logger(__name__)


# https://docs.djangoproject.com/en/5.0/topics/db/managers/
# A Manager is the interface through which database query operations are provided to Django models.
# Mangers are intended to be used to encapsulate logic for managing collections of objects.
# At least one Manager exists for every model in a Django application."

if TYPE_CHECKING:
    from requests import Response

    from ubdc_airbnb import models as app_models


class AirBnBResponseManager(models.Manager):

    def fetch_response(
        self,
        type: "app_models.AirBnBResponseTypes",
        task_id: str | None = None,
        **kwargs,
    ):
        """Make a request to the airbnb API and create an AirBnBResponse object from the response.

        If an exception is raised during the request, it is caught and the response is saved in the database.
        The exception is then re-raised."""
        from ubdc_airbnb.airbnb_interface.airbnb_api import AirbnbApi
        from ubdc_airbnb.models import AirBnBResponseTypes

        if type != AirBnBResponseTypes.search:
            assert "asset_id" in kwargs

        airbnb_client = AirbnbApi(proxy=settings.AIRBNB_PROXY)

        match type:
            case AirBnBResponseTypes.bookingQuote:
                method_name = "get_booking_details"
                asset_id = kwargs.pop("asset_id")
                kwargs.update(listing_id=asset_id)
                assert "listing_id" in kwargs
            case AirBnBResponseTypes.calendar:
                method_name = "get_calendar"
                asset_id = kwargs.pop("asset_id")
                kwargs.update(listing_id=asset_id)
                assert "listing_id" in kwargs
            case AirBnBResponseTypes.review:
                method_name = "get_reviews"
                asset_id = kwargs.pop("asset_id")
                kwargs.update(listing_id=asset_id)
                assert "listing_id" in kwargs
            case AirBnBResponseTypes.listingDetail:
                method_name = "get_listing_details"
                asset_id = kwargs.pop("asset_id")
                kwargs.update(listing_id=asset_id)
                assert "listing_id" in kwargs
            case AirBnBResponseTypes.search:
                method_name = "get_homes"
                # kwargs.pop("asset_id")
            case AirBnBResponseTypes.searchMetaOnly:
                method_name = "bbox_metadata_search"
                # kwargs.pop("asset_id")
            case AirBnBResponseTypes.userDetail:
                method_name = "get_user"
                asset_id = kwargs.pop("asset_id")
                kwargs.update(user_id=asset_id)
                assert "user_id" in kwargs
            case _:
                raise ValueError(f"Invalid _type: {type}")

        method = getattr(airbnb_client, method_name)

        if method is None:
            raise Exception(f"could not find reference: {method_name}")

        response = method(**kwargs)

        listing_id = kwargs.get("listing_id", None)

        obj = self.create_from_response(
            response=response,
            type=type,
            task_id=task_id,
            listing_id=listing_id,
        )

        # The response-object has been created successfully.
        return obj

    def create_from_response(
        self,
        response: "Response",
        type: str,
        task_id: str | None = None,
        listing_id: int | None = None,
    ):
        from ubdc_airbnb.models import UBDCTask

        should_raise = None

        def encapsulate_payload(response: "Response") -> dict:
            "Tries to encapsulate the response in a dict."
            import base64

            payload = {}
            base64_str = base64.b64encode(response.content).decode("utf-8") if response.content else None
            try:
                text = response.text
            except Exception as e:  # noqa
                text = "could not be serialised"
            payload.update(
                context_text=text,
                base64_str=base64_str,
            )
            return payload

        status_code = response.status_code
        try:
            payload = response.json()
        except JSONDecodeError as e:
            logger.info(f"JSONDecodeError when parsing response")
            payload = encapsulate_payload(response)
        except TypeError as e:
            # response data is NoneType
            logger.info(f"TypeError when parsing response")
            payload = encapsulate_payload(response)
        except AttributeError as e:
            # there are cases where the body comes back empty.
            logger.info(f"AttributeError when parsing response")
            payload = encapsulate_payload(response)

        match status_code:
            case 200:
                # 200 OK
                pass
            case 429:
                # 429 Too Many Requests; pass for retry
                should_raise = UBDCRetriableError("429 error, retrying", response)
            case 403:
                # 403 Forbidden. We want to know about this.
                pass
            case 503:
                # 503 Service Unavailable?
                should_raise = UBDCRetriableError("503 error, retrying", response)
            case _:
                # TODO: [EASY-FIX] Consider doing a db entry for this. Or Sentry logging.
                req = response.request
                logger.info(f"Un-expected status")
                logger.info(f"Response: {response.text}")
                logger.info(f"Request: {req.method} {status_code} {req.url}")
                logger.info(f"Headers:")
                for k, v in req.headers.items():
                    logger.info(f"{k}: {v}")

        ubdc_task = UBDCTask.objects.filter(task_id=task_id).first()

        params = {}
        params.update(
            _type=type,
            listing_id=listing_id,
            status_code=status_code,
            request_headers=dict(**response.request.headers),
            payload=payload,
            url=response.url,
            query_params=query_params_from_url(response.url),
            seconds_to_complete=response.elapsed.seconds,
        )
        if task_id:
            # If we have a task_id, we can link the response to the task.
            obj, _ = self.update_or_create(ubdc_task=ubdc_task, defaults={**params})
        if not task_id:
            # If we don't have a task_id, the response came from a standalone request.
            obj = self.create(**params)

        if should_raise:
            logger.info(f"SELECT * FROM app_airbnbresponse WHERE id = {obj.id}")
            raise should_raise

        try:
            response.raise_for_status()
        except ProxyError as e:
            raise UBDCRetriableError("ProxyError") from e
        except HTTPError as e:
            pass

        return obj


class AirBnBListingManager(models.Manager):

    def for_purpose(
        self,
        purpose: Literal["calendar", "reviews", "listing_details"],
    ) -> 'AirBnBListingManager':
        """Returns a QS with all the listings ids within an enabled AOI"""

        from ubdc_airbnb.models import AOIShape

        match purpose:
            case "listing_details":
                list_aoi = AOIShape.objects.filter(collect_listing_details=True)
            case "calendar":
                list_aoi = AOIShape.objects.filter(collect_calendars=True)
            case "reviews":
                list_aoi = AOIShape.objects.filter(collect_reviews=True)
            case _:
                raise ValueError("invalid argument")

        # Create a union of all the AOIs
        # Warning: This might create a degenerate polygon.
        # I am not aware of any issues with this, but it's worth keeping in mind.
        geom = list_aoi.aggregate(union=ST_Union("geom_3857"))["union"]
        qs_listings = self.filter(geom_3857__intersects=geom)

        return qs_listings

    def create_from_data(self, listing_id: int, lon: float, lat: float) -> "app_models.AirBnBListing":
        """Create an AirBnBListing Point from data. The returned object is saved in the Database
        :param listing_id:
        :param lon: Longitude in EPSG:4326
        :param lat: Latitude in EPSG:4326
        """

        # prev_location = app_models.AirBnBListing.objects.get(listing_id=listing_id).geom_3857
        _4326_point = make_point(lon, lat, 4326)
        _3857_point = reproject(_4326_point, to_srid=3857)
        obj = self.create(listing_id=listing_id, geom_3857=_3857_point)

        return obj


class UserManager(models.Manager):

    def get_or_create(
        self,
        defaults: MutableMapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> tuple["app_models.AirBnBUser", bool]:
        "Gets the user or creates a placeholder user if it does not exist."

        from ubdc_airbnb.model_defaults import (
            AIRBNBUSER_FIRST_NAME,
            AIRBNBUSER_LOCATION,
        )

        model_defaults = {
            "first_name": AIRBNBUSER_FIRST_NAME,
            "airbnb_listing_count": 0,
            "verifications": [],
            "picture_url": "",
            "location": AIRBNBUSER_LOCATION,
        }
        defaults = {**model_defaults, **(defaults or {})}

        return super().get_or_create(defaults=defaults, **kwargs)

    def create_from_response(
        self,
        ubdc_response: "app_models.AirBnBResponse",
        user_id: int,
    ) -> "app_models.AirBnBUser":
        """Create an AirBnBUser from an airbnb response or a placeholder AirbnbUser from just hte user_id"""

        if user_id is None and ubdc_response is None:
            raise ValueError("Both user_id and airbnb_response are None")

        if ubdc_response.status_code > 299:
            payload = {}
            user_data = {}
        else:
            payload = ubdc_response.payload
            user_data = payload["user"]

        # extract pics
        try:
            picture_url = airbnb_response_parser.profile_pics(payload)[0].split("?")[0]
        except IndexError:
            picture_url = ""
            print(f'!!! WARNING !!! Could not find a picture_url for {user_data.get("id", user_id)}')

        obj = self.create(
            user_id=user_data.get("id", user_id),
            first_name=user_data.get("first_name", "UNKNOWN-DUMMY"),
            about=user_data.get("about", "UNKNOWN-DUMMY"),
            airbnb_listing_count=user_data.get("listings_count", 0),
            verifications=user_data.get("verifications", []),
            picture_url=picture_url,
            created_at=user_data.get("created_at", None),
            location=user_data.get("location", "UNKNOWN-DUMMY"),
        )
        obj.responses.add(ubdc_response)
        obj.save()

        return obj


class UBDCGridManager(models.Manager):

    def intersect_with_aoi(self, aoi_list: "List[app_models.AOIShape]"):
        "Get the grids that intersect with the aois."
        q = models.Q()
        for aoi in aoi_list:
            q |= models.Q(geom_3857__intersects=aoi.geom_3857)

        qs = self.filter(q)
        qs = qs.order_by("quadkey")
        qs = qs.distinct("quadkey")

        return qs

    def has_quadkey(self, quadkey) -> bool:
        return self.filter(quadkey=quadkey).exists()

    def model_from_quadkey(self, quadkey: str) -> "app_models.UBDCGrid":
        """Make an UBDCGrid object and return a ref of it."""
        tile = mercantile.quadkey_to_tile(quadkey)
        return self.model_from_tile(tile)

    def create_from_quadkey(self, quadkey: str):
        tile = mercantile.quadkey_to_tile(quadkey)
        return self.create_from_tile(tile)

    def model_from_tile(
        self,
        tile: mercantile.Tile,
    ) -> "app_models.UBDCGrid":
        """Make an UBDCGrid object and return a ref of it."""
        quadkey = mercantile.quadkey(tile)
        bbox = list(mercantile.xy_bounds(*tile))
        min_x, min_y, max_x, max_y = bbox
        mid_x = min_x + max_x / 2
        mid_y = min_y + max_y / 2
        geom_3857 = GEOSPolygon.from_bbox(bbox)

        return self.model(
            geom_3857=geom_3857,
            quadkey=quadkey,
            bbox_ll_ur=",".join(map(str, bbox)),
            tile_x=tile.x,
            tile_y=tile.y,
            tile_z=tile.z,
            area=geom_3857.area,
            x_distance_m=postgis_distance_a_to_b((min_x, mid_y), (max_x, mid_y)),
            y_distance_m=postgis_distance_a_to_b((mid_x, min_y), (mid_x, max_y)),
        )

    # TODO: [EASY-FIX] This is a get or create, but branded as get.
    def create_from_tile(self, tile: mercantile.Tile) -> "app_models.UBDCGrid":
        """Create an UBDCGrid entry and return a ref of it."""
        obj = self.model_from_tile(tile)
        if self.has_quadkey(obj.quadkey):
            return self.get(quadkey=obj.quadkey)
        obj.save()
        return obj
