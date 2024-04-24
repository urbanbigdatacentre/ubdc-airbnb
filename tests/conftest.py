import inspect
from datetime import timezone
from typing import Any
from unittest.mock import Mock

import pytest

UTC = timezone.utc


@pytest.fixture(scope="function")
def geojson_gen():
    "A fixture that yields AOIs in GeoJSON format"
    from pathlib import Path

    test_aoi_folder = Path(__file__).parent / "test_aois"
    assert test_aoi_folder.exists()
    assert test_aoi_folder.is_dir()

    yield [f.read_text() for f in test_aoi_folder.glob("*.geojson")]


@pytest.fixture(scope="function")
def mock_airbnb_client(mocker, faker):
    # from ubdc_airbnb.airbnb_interface import airbnb_api
    from requests import Request, Response
    from requests.exceptions import HTTPError

    from ubdc_airbnb.models import AirBnBResponseTypes

    class MockResponse:
        def __init__(
            self,
            response_type: AirBnBResponseTypes,
            status_code: int = 200,
            json_data: dict[str, Any] = {"test": "test"},
            headers: dict[str, Any] = {"x-header": "test"},
            **kwargs,
        ):
            self.status_code = status_code
            self.json_data = json_data
            self.listing_id = kwargs.get("listing_id", None)
            self.headers = headers

            match response_type:
                case AirBnBResponseTypes.listingDetail:
                    self.listing_id = kwargs.get("listing_id", 12345)
                    self._url = f"http://test.com/?listing_id={self.listing_id}&param=2"
                case AirBnBResponseTypes.review:
                    self.listing_id = kwargs.get("listing_id", 12345)
                    self.offset = kwargs.get("offset", 0)
                    self.limit = kwargs.get("limit", 100)
                    self._url = f"https://test.com/api/v2/reviews?_order=language_country&listing_id={self.listing_id}&_offset={self.offset}&role=all&_limit={self.limit}&_format=for_mobile_client"
                case _:
                    self._url = "http://test.com"

        def raise_for_status(self):
            if self.status_code != 200:
                raise HTTPError(f"Mock-Exception code: {self.status_code}")

        def json(self):
            return self.json_data

        @property
        def text(self):
            return str(self.json_data)

        @property
        def url(self):
            return self._url

        @property
        def elapsed(self):
            return faker.time_delta()

        @property
        def request(self):
            return Mock(spec=Request, headers={"Test": "Test"})

    def review_side_effect(*args, **kwargs):
        # mref = inspect.currentframe().f_back.f_locals.get("self")  # type: ignore
        # assert mref
        # times_called: int = mref.call_count
        status_code = 200
        review_id = faker.random_int(min=300000, max=1000000)
        author_id = faker.random_int(min=300000, max=1000000)
        recipient_id = faker.random_int(min=300000, max=1000000)
        json_data = {
            "reviews": [
                {
                    "id": review_id,
                    "role": "guest",
                    "author": {
                        "id": author_id,
                        "first_name": faker.first_name(),
                        "picture_url": faker.image_url(),
                    },
                    "id_str": str(review_id),
                    "comments": faker.text(),
                    "author_id": author_id,
                    "recipient_id": recipient_id,
                    "recipient": {
                        "id": recipient_id,
                        "first_name": faker.first_name(),
                        "picture_url": faker.image_url(),
                    },
                    "created_at": faker.iso8601(tzinfo=UTC),
                }
            ],
            "metadata": {
                "reviews_count": 350,
                "should_show_review_translations": False,
            },
        }
        rv = MockResponse(
            response_type=AirBnBResponseTypes.review,
            status_code=status_code,
            json_data=json_data,
            **kwargs,
        )
        return rv, rv.json()

    def user_side_effect(*args, **kwargs):
        mref = inspect.currentframe().f_back.f_locals.get("self")  # type: ignore
        # get the call count
        times_called: int = mref.call_count  # type: ignore
        match times_called:
            case 1:
                status_code = 200
            case 2:
                status_code = 404
            case 3:
                status_code = 503
                headers = {"X-Crawlera-Error": "banned"}
                e = HTTPError("Mock-Exception code: 503")
                e.response = MockResponse(
                    response_type=AirBnBResponseTypes.userDetail, status_code=503, headers=headers, **kwargs
                )
                raise e
            case _:
                status_code = 200

        json_data = {
            "user": {
                "id": faker.random_int(min=300000, max=1000000),
                "first_name": faker.first_name(),
                "picture_url": faker.image_url(),
                "is_superhost": faker.boolean(),
                "location": faker.country(),
                "listings_count": faker.random_int(min=0, max=100),
                "reviewee_count": faker.random_int(min=0, max=100),
                "verifications": [faker.word() for _ in range(3)],
                "created_at": faker.iso8601(tzinfo=UTC),
                "picture_urls": [faker.image_url() for _ in range(3)],
            }
        }
        rv = MockResponse(
            response_type=AirBnBResponseTypes.userDetail,
            status_code=status_code,
            json_data=json_data,
            **kwargs,
        )
        return rv, rv.json()

    def calendar_side_effect(
        listing_id,
        status_code=200,
        json_data={},
        headers={},
        **kwargs,
    ):

        import inspect

        json_data = {"test": "test"}
        # how any times this function has been called?
        # Ask the parent mock object.
        # Obviouslly, this is a hack and depents that this function is called from a mock object
        # get a ref to parent mock object
        mref = inspect.currentframe().f_back.f_locals.get("self")  # type: ignore
        # get the call count
        times_called: int = mref.call_count  # type: ignore

        # Special Rules for listing_ids starting with 8:
        # every odd call returns 503
        # every even call returns 200
        if str(listing_id).startswith("8"):
            if times_called % 2 == 1:
                # 503
                status_code = 503
                headers.update({"X-Crawlera-Error": "banned"})
                response = MockResponse(
                    response_type=AirBnBResponseTypes.calendar,
                    status_code=status_code,
                    json_data=json_data,
                    listing_id=listing_id,
                    headers=headers,
                    **kwargs,
                )
                e = HTTPError("Mock-Exception code: 503")
                e.response = response
                raise e
            else:
                rv = MockResponse(
                    response_type=AirBnBResponseTypes.calendar,
                    status_code=200,
                    json_data=json_data,
                    listing_id=listing_id,
                    headers=headers,
                    **kwargs,
                )
                return rv, rv.json()
        else:
            rv = MockResponse(
                response_type=AirBnBResponseTypes.calendar,
                status_code=status_code,
                json_data=json_data,
                listing_id=listing_id,
                headers=headers,
                **kwargs,
            )

            return rv, rv.json()

    def get_homes_side_effect(*args, **kwargs):
        # how any times this function has been called?
        # Ask the parent mock object.
        # Obviouslly, this is a hack and depents that this function is called from a mock object
        # get a ref to parent mock object
        mref = inspect.currentframe().f_back.f_locals.get("self")  # type: ignore
        # get the call count
        times_called: int = mref.call_count  # type: ignore

        status_code = 200
        match times_called:
            case 1:
                listings_number = 10000
            case 2:
                listings_number = 1000
            case 3:
                listings_number = 100
            case 4:
                listings_number = 10
            case _:
                listings_number = 1

        has_next_page = True if listings_number >= 25 else False
        listings = [
            {
                "listing": {
                    "id_str": faker.pystr_format(string_format="##################"),  # 18 chars
                    "lat": faker.pyfloat(
                        max_value=kwargs.get("north", 10),
                        min_value=kwargs.get("south", -10),
                    ),
                    "lng": faker.pyfloat(
                        min_value=kwargs.get("west", -10),
                        max_value=kwargs.get("east", 10),
                    ),
                }
            }
            for x in range(min(listings_number, 50))
        ]
        json_data = {
            "explore_tabs": [
                {"home_tab_metadata": {"listings_count": listings_number}},
                {"pagination_metadata": {"has_next_page": has_next_page}},
                {"sections": [[], [], {"listings": listings}]},
            ],
        }

        rv = MockResponse(
            response_type=AirBnBResponseTypes.search,
            status_code=status_code,
            json_data=json_data,
            listing_id=None,
            headers={},
            **kwargs,
        )

        return rv, rv.json()

    def get_listing_details_effect(*args, **kwargs):

        def gen_fake_user():
            return {
                "id": faker.random_int(min=300000, max=1000000),
                "first_name": faker.first_name(),
                "picture_url": faker.image_url(),
                "is_superhost": faker.boolean(),
            }

        status_code = 200
        json_data = {
            "pdp_listing_detail": {
                "primary_host": gen_fake_user(),
                "additional_hosts": [gen_fake_user() for _ in range(3)],
            }
        }
        # listing_id = kwargs.get("listing_id", 12345)
        rv = MockResponse(
            AirBnBResponseTypes.listingDetail,
            status_code=status_code,
            # listing_id=listing_id,
            json_data=json_data,
            **kwargs,
        )

        return rv, rv.json()

    m = mocker.patch("ubdc_airbnb.airbnb_interface.airbnb_api.AirbnbApi", autospec=True)
    m().get_homes.side_effect = get_homes_side_effect
    m().get_listing_details.side_effect = get_listing_details_effect
    m().get_calendar.side_effect = calendar_side_effect
    m().get_user.side_effect = user_side_effect
    m().get_reviews.side_effect = review_side_effect
    yield m


@pytest.fixture(scope="session")
def celery_enable_logging():
    return True


@pytest.fixture(scope="session")
def celery_parameters():
    from celery import Celery

    from ubdc_airbnb.task_managers import BaseTaskWithRetry

    return {
        "broker": "memory://",
        "backend": "django-db",
        "task_cls": BaseTaskWithRetry,
        "worker_cancel_long_running_tasks_on_connection_loss": True,
    }


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    # place here any pre-db provisioning
    return


@pytest.fixture()
def aoishape_model(db):
    from django.apps import apps as django_apps

    model = django_apps.get_model("app.AOIShape")
    return model


@pytest.fixture()
def responses_model(db):
    from django.apps import apps as django_apps

    model = django_apps.get_model("app.AirBnBResponse")
    return model


@pytest.fixture()
def ubdcgrid_model(db):
    from django.apps import apps as django_apps

    model = django_apps.get_model("app.UBDCGrid")
    assert model.objects.count() == 0
    return model


@pytest.fixture()
def user_model(db):
    from django.apps import apps as django_apps

    model = django_apps.get_model("app.AirBnBUser")
    return model


@pytest.fixture()
def listings_model(db):
    from django.apps import apps as django_apps

    model = django_apps.get_model("app.AirBnBListing")
    return model


@pytest.fixture(scope="session")
def celery_worker_parameters():
    return {
        "worker_cancel_long_running_tasks_on_connection_loss": True,
        "concurrency": 1,
        "perform_ping_check": True,
    }


@pytest.fixture(scope="session")
def celery_worker_pool():
    return "threads"


@pytest.fixture(scope="session")
def celery_includes():
    return [
        "ubdc_airbnb.tasks",
    ]


@pytest.fixture(scope="function")
def celery_app(celery_app):
    yield celery_app
