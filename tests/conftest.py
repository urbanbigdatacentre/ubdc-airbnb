from datetime import timezone
from unittest.mock import Mock

import pytest
from faker import Faker

fake = Faker()
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
def mock_airbnb_client(mocker):
    # from ubdc_airbnb.airbnb_interface import airbnb_api
    from unittest.mock import MagicMock

    from requests import Request
    from requests.exceptions import HTTPError

    class MockResponse:
        def __init__(self, status_code, json_data, listing_id, headers, **kwargs):
            self.status_code = status_code
            self.json_data: dict = json_data
            self.listing_id: int = listing_id
            self.headers = headers

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
            if self.listing_id:
                return f"http://test.com/?listing_id={self.listing_id}&param=2"
            return "http://test.com/search?"

        @property
        def elapsed(self):
            return fake.time_delta()

        @property
        def request(self):
            return Mock(spec=Request, headers={"Test": "Test"})

    class MockRequest:
        # TODO: populate?
        pass

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
                    status_code=status_code,
                    json_data=json_data,
                    listing_id=listing_id,
                    headers=headers,
                    kwargs=kwargs,
                )
                e = HTTPError("Mock-Exception code: 503")
                e.response = response
                raise e
            else:
                rv = MockResponse(
                    status_code=200,
                    json_data=json_data,
                    listing_id=listing_id,
                    headers=headers,
                    kwargs=kwargs,
                )
                return rv, rv.json()
        else:
            rv = MockResponse(
                status_code=status_code,
                json_data=json_data,
                listing_id=listing_id,
                headers=headers,
                kwargs=kwargs,
            )

            return rv, rv.json()

    def get_homes_side_effect(*args, **kwargs):
        import inspect

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
                    "id_str": fake.pystr_format(string_format="##################"),  # 18 chars
                    "lat": fake.pyfloat(
                        max_value=kwargs.get("north", 10),
                        min_value=kwargs.get("south", -10),
                    ),
                    "lng": fake.pyfloat(
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
            status_code=status_code,
            json_data=json_data,
            listing_id=None,
            headers={},
            kwargs=kwargs,
        )

        return rv, rv.json()

    from ubdc_airbnb.airbnb_interface.airbnb_api import AirbnbApi

    m = mocker.patch.multiple(
        AirbnbApi,
        get_homes=MagicMock(side_effect=get_homes_side_effect),
        get_calendar=MagicMock(side_effect=calendar_side_effect),
    )

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
