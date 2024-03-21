import functools
import json
from collections import namedtuple
from datetime import datetime
from hashlib import md5
from typing import Dict, Iterator, Mapping, Optional, Tuple, Type
from uuid import uuid4

import requests
from django.conf import settings
from jsonpath_ng import parse as json_parse
from more_itertools import chunked
from requests import Response

from ubdc_airbnb.errors import MissingParameterError, NoBookingDatesError

POINT = namedtuple("POINT", "x y")
BBOX = namedtuple("BBOX", "upper_left lower_right")
AIRBNB_PUBLIC_API_KEY = "d306zoyjsyarp7ifhu67rjxn52tv0t20"


def attach_response_obj(r: requests.Response, this_object: "AirbnbApi", *args, **kwargs):
    """Response Middleware"""
    this_object.response = r


class AirbnbApi(object):
    """ Base API class
    # >>> api = Api(access_token=os.environ.get("AIRBNB_ACCESS_TOKEN"))
    # >>> api = Api()
    # >>> api.get_homes("Lisbon, Portugal") # doctest: +ELLIPSIS
    # {...}
    # >>> api.get_homes(gps_lat=55.6123352, gps_lng=37.7117917) # doctest: +ELLIPSIS
    # {...}
    # >>> api.get_homes("Lisbon, Portugal", checkin=datetime.datetime.now().strftime("%Y-%m-%d"), \
    #     checkout=(datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")) # doctest: +ELLIPSIS
    # {...}
    # >>> api.get_calendar(975964) # doctest: +ELLIPSIS
    # {...}
    # >>> api.get_reviews(975964) # doctest: +ELLIPSIS
    # {...}
    # >>> api = Api(randomize=True)
    # >>> api.get_listing_details(975964) # doctest: +ELLIPSIS
    {...}
    """

    def __init__(
        self,
        api_key: str | None = None,
        proxy: str | None = None,
        extra_headers: Dict[str, str] | None = None,
        randomize: bool = True,
    ):
        """

        :param api_key: The api key to access airbnb.
                If none, the 'AIRBNB_API_KEY' env key will be used.
                If it is not set the default key will be used.
        :param proxy: proxy ip to use for the requests.
        :param randomize: randomise certain identities to further anonymize the request (experimental).
        """

        self._airbnb_api_key: str = ""
        self._federated_search_session_id: Optional[str] = None
        self._client_session_id: Optional[str] = None
        self._session: requests.Session = requests.Session()
        self._response: Optional[requests.Response] = None
        self._user_agent: Optional[str] = None
        self._udid: str = "9120210f8fb1ae837affff54a0a2f64da821d227"
        self._uuid: str = uuid4().__str__().upper()
        self.randomize: bool = randomize
        self.currency: str = "GBP"
        self.locale: str = "en"

        self._session.hooks = {"response": functools.partial(attach_response_obj, this_object=self)}

        self._session.headers = {
            "accept": "application/json",
            "accept-encoding": "br, gzip, deflate",
            "content-type": "application/json; charset=UTF-8",
            # "x-airbnb-api-key": -> check bellow
            "user-agent": self.user_agent,
            # "x-airbnb-screensize": "w=375.00;h=812.00",
            # "x-airbnb-carrier-name": "T-Mobile",
            # "x-airbnb-network-type": "wifi",
            "x-airbnb-oauth-token": "public",
            "x-airbnb-currency": self.currency,
            "x-airbnb-locale": self.locale,
            # "x-airbnb-carrier-country": "us",
            "accept-language": "en-GB",
            # "airbnb-device-id": self.udid,
            "x-airbnb-advertising-id": self.uuid,
        }

        self._session.verify = False
        if api_key:
            self.airbnb_api_key = api_key
        else:
            self.airbnb_api_key = AIRBNB_PUBLIC_API_KEY

        if proxy:
            print(f"Using proxy: {proxy}")
            self._session.proxies = {
                "http": proxy,
                "https": proxy,
            }
        if extra_headers:
            self._session.headers.update(extra_headers)

    @classmethod
    def param_factory(cls) -> dict:
        """Returns a dictionary with the most common params. Makes requests more verbose."""
        params = {}
        params.update(
            version="1.6.5",
            timezone_offset=0,
            metadata_only=False,
            _format="for_explore_search_web",
            is_standard_search=True,
            satori_version="1.1.9",
        )

        return params

    @property
    def response(self):
        return self._response

    @response.setter
    def response(self, value):
        self._response = value

    def get_session(self):
        return self._session

    @property
    def federated_search_session_id(self):
        return self._federated_search_session_id

    @federated_search_session_id.setter
    def federated_search_session_id(self, value):
        self._federated_search_session_id = value

    @property
    def client_session_id(self):
        return self._client_session_id

    @client_session_id.setter
    def client_session_id(self, value):
        self._client_session_id = value

    @property
    def airbnb_api_key(self):
        return self._airbnb_api_key

    @airbnb_api_key.setter
    def airbnb_api_key(self, value):
        self._airbnb_api_key = value
        self._session.headers["x-airbnb-api-key"] = self._airbnb_api_key

    @property
    def user_agent(self) -> str:
        return self._user_agent

    @user_agent.setter
    def user_agent(self, value):
        self._user_agent = value
        self._session.headers["user-agent"] = self._user_agent

    @property
    def uuid(self):
        return self._uuid

    @uuid.setter
    def uuid(self, value):
        """uuid is used for advertisement id?"""
        self._uuid = value
        self._session.headers["x-airbnb-advertising-id"] = self._uuid

    @property
    def udid(self):
        return self._udid

    @udid.setter
    def udid(self, value):
        self._udid = value
        self._session.headers["airbnb-device-id"] = self._udid

    def get_calendar(
        self,
        listing_id,
        starting_month=None,
        starting_year=None,
        calendar_months=12,
    ) -> tuple[Response, dict]:
        """
        Get availability calendar for a given listing. Returns the response and the json payload.
        """

        if not starting_month:
            starting_month = datetime.utcnow().month
        if not starting_year:
            starting_year = datetime.utcnow().year

        params = {
            "year": str(starting_year),
            "listing_id": str(listing_id),
            "_format": "with_conditions",
            "count": str(calendar_months),
            "month": str(starting_month),
        }

        r = self._session.get(settings.AIRBNB_API_ENDPOINT + "/v2/calendar_months", params=params)
        r.raise_for_status()

        return r, r.json()

    def get_reviews(self, listing_id, offset=0, limit=20) -> (Response, dict):
        """
        Get reviews for a given listing, currently limit is up to 100.
        """
        params = {
            "_order": "language_country",
            "listing_id": str(listing_id),
            "_offset": str(offset),
            "role": "all",
            "_limit": str(limit),
            "_format": "for_mobile_client",
        }

        r = self._session.get(settings.AIRBNB_API_ENDPOINT + "/v2/reviews", params=params)
        r.raise_for_status()

        return r, r.json()

    def iterate_reviews(self, listing_id, by=20):
        has_next_page = True
        c = 1
        while has_next_page:
            reviews = self.get_reviews(listing_id, offset=c * by, limit=by)
            reviews_count = reviews["metadata"]["reviews_count"]
            c += 1
            has_next_page = reviews_count // (c * by)
            yield reviews

    def get_homes(
        self,
        query: str | None = None,
        west: float | None = None,
        south: float | None = None,
        east: float | None = None,
        north: float | None = None,
        checkin=None,
        checkout=None,
        items_offset=0,
        items_per_grid=25,
        metadata_only=False,
    ) -> tuple[Response, dict]:
        """
        TODO: Update Docstring
        """

        is_geographic_search = False

        params = {
            "toddlers": "0",
            "infants": "0",
            "is_guided_search": "true",
            "version": "1.7.0",
            "section_offset": "0",
            "items_offset": str(items_offset),
            "adults": "0",
            "screen_size": "large",
            "source": "explore_tabs",
            "items_per_grid": str(items_per_grid),
            "_format": "for_explore_search_native",
            "refinement_paths[]": "/homes",
            "timezone_offset": "0",
            "satori_version": "1.1.1",
            # if this true, only the metadata of the search will come back. (i.e how many results)
            "metadata_only": metadata_only,
            "key": self.airbnb_api_key,
        }

        if self.federated_search_session_id:
            params.update({"federated_search_session_id": self.federated_search_session_id})

        if self.client_session_id:
            params.update(client_session_id=self.client_session_id)

        if all(x is not None for x in [west, south, east, north]):
            is_geographic_search = True

        if not query and not is_geographic_search:
            raise MissingParameterError("Missing query or bounding box")

        if query:
            params["query"] = query

        if is_geographic_search:
            params["ne_lat"] = north
            params["ne_lng"] = east
            params["sw_lat"] = south
            params["sw_lng"] = west

            params["search_by_map"] = True

        if checkin and checkout:
            params["checkin"] = checkin
            params["checkout"] = checkout

        r = self._session.get(
            settings.AIRBNB_API_ENDPOINT + "/v2/explore_tabs",
            params=params,
        )
        r.raise_for_status()

        return r, r.json()

    def get_listing_details(
        self,
        listing_id: int,
    ):
        params = {
            "adults": "0",
            "_format": "for_native",
            "infants": "0",
            "children": "0",
        }

        r = self._session.get(
            settings.AIRBNB_API_ENDPOINT + "/v2/pdp_listing_details/" + str(listing_id),
            params=params,
        )
        r.raise_for_status()

        return r, r.json()

    def iterate_homes(
        self,
        query=None,
        checkin=None,
        checkout=None,
        south=None,
        west=None,
        east=None,
        north=None,
        per=50,
    ) -> Iterator[Tuple[int, Iterator[Mapping[int, int]]]]:
        # do I need to use the same ip?
        page = 0
        while True:
            response, payload = self.get_homes(
                query,
                checkin=checkin,
                checkout=checkout,
                north=north,
                south=south,
                west=west,
                east=east,
                items_offset=page * per,
                items_per_grid=per,
            )

            matches = json_parse(r"$..explore_tabs..sections..listing[id,lat,lng]").find(payload)
            res_gen = chunked(matches, 3, strict=True)
            yield page, res_gen

            page += 1
            pagination_metadata = payload["explore_tabs"][0]["pagination_metadata"]
            self.federated_search_session_id = payload["metadata"]["federated_search_session_id"]

            has_next_page = pagination_metadata["has_next_page"]

            if has_next_page is False:
                break

        # clear federated_search_session_id
        self.federated_search_session_id = None

    def get_user(self, user_id):
        params = {}
        r = self._session.get(settings.AIRBNB_API_ENDPOINT + f"/v2/users/{user_id}", params=params)
        r.raise_for_status()
        self.response = r

        return r, r.json()

    def bbox_metadata_search(
        self,
        store_federated_search_session_id: bool = False,
        **kwargs,
    ) -> Tuple[Response, Dict]:
        """Return the number_results of this query.

        :param store_federated_search_session_id:
            Save the federated search id. Default is False, as this number is considered indicative.
        """

        kwargs["metadata_only"] = True
        response, payload = self.get_homes(**kwargs)
        if store_federated_search_session_id:
            self.federated_search_session_id = self.response.json()["metadata"]["federated_search_session_id"]

        return response, payload

    def get_booking_details(
        self,
        listing_id: int,
        calendar: dict = None,
        start_search_from: Type[datetime.date] = None,
    ):
        """

        :param listing_id: Listing Id
        :param calendar: Parsed Calendar
        :param start_search_from: date or datetime to start the search from for an available booking
        :return:
        """

        start_search_from = start_search_from or datetime.utcnow()

        params = {}
        params.update(
            _format="for_web_with_date",
            # _intents="p3_book_it",
            # _interaction_type="dateChanged",
            # _p3_impression_id="p3_1584810410_Y/maqgJf8Eg/aTiU",
            # _parent_request_uuid="dbded0fc-7a0d-4fbc-8bf7-07e7e59e8f7b",
            # check_in="2020-04-08",
            # check_out="2020-04-09",
            currency="GBP",
            # federated_search_id="d12c5fa3-0200-4a65-b0c5-42a1d3449092",
            # force_boost_unc_priority_message_type="",
            guests="1",
            key=self.airbnb_api_key,
            listing_id=str(listing_id),
            locale="en-GB",
            number_of_adults="1",
            number_of_children="0",
            number_of_infants="0",
            search_id="d5292adc-8660-75f2-b984-7a0cfc0dd6d5",
            show_smart_promotion="0",
        )

        def find_checkin_checkout(listing_calendar: dict):
            cal_parser = json_parse("calendar_months[*].days[*]")
            stays = 0
            min_nights = 0
            check_in = None
            check_out = None
            elem = cal_parser.find(listing_calendar)
            for entry in elem:
                date = datetime.strptime(entry.value["date"], "%Y-%m-%d")
                if date <= datetime.utcnow():
                    continue

                stays += 1
                if entry.value["available_for_checkin"]:
                    if check_in is None:
                        check_in = date
                        min_nights = entry.value["min_nights"]
                        stays = 1
                        continue

                    if check_in is not None:
                        if check_in.strftime("%Y-%m-%d") == entry.value["date"]:
                            continue
                        if stays >= min_nights:
                            check_out = date
                            break
            else:
                check_in = None

            if check_in is None or check_out is None:
                bstr = json.dumps(listing_calendar, sort_keys=True).encode()
                raise NoBookingDatesError(f"calendar md5_hexdigest: {md5(bstr).hexdigest()}")

            return check_in.strftime("%Y-%m-%d"), check_out.strftime("%Y-%m-%d")

        if calendar is None:
            calendar = self.get_calendar(listing_id)
        checkin, checkout = find_checkin_checkout(calendar)
        params.update(check_in=checkin, check_out=checkout)
        r = self._session.get(
            settings.AIRBNB_API_ENDPOINT + f"/v2/pdp_listing_booking_details",
            params=params,
        )
        r.raise_for_status()

        return r, r.json()


__all__ = [
    "AirbnbApi",
]
