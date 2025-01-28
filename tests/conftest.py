from datetime import timezone
from queue import Empty as ExcEmptyQueue
from queue import Queue
from typing import Any

import pytest

UTC = timezone.utc


@pytest.fixture(scope="function")
def response_queue():
    return Queue()


@pytest.fixture(scope="function")
def geojson_gen():
    "A fixture that yields AOIs in GeoJSON format"
    from pathlib import Path

    test_aoi_folder = Path(__file__).parent / "test_aois"
    assert test_aoi_folder.exists()
    assert test_aoi_folder.is_dir()

    yield [f.read_text() for f in test_aoi_folder.glob("*.geojson")]


@pytest.fixture(scope="function")
def mock_airbnb_client(mocker, faker, response_queue):
    # from ubdc_airbnb.airbnb_interface import airbnb_api
    from requests import Request
    from requests.exceptions import HTTPError

    from ubdc_airbnb.models import AirBnBResponseTypes

    class MockResponse:
        def __init__(
            self,
            response_type: AirBnBResponseTypes,
            status_code: int = 200,
            content: bytes | None = None,
            # text: str | None = None,
            # json_data: dict[str, Any] = {"test": "test"},
            headers: dict[str, Any] = {"x-header": "test"},
            **kwargs,
        ):
            self.status_code = status_code
            self.content: bytes | None = content
            self.listing_id = kwargs.get("listing_id", None)
            self._headers = headers

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
            exc = HTTPError(f"Mock-Exception code: {self.status_code}", response=self)  # type: ignore
            if self.status_code != 200:
                raise exc

        @property
        def headers(self):
            response_headers = {}
            if self.status_code == 503:
                response_headers["X-Crawlera-Error"] = "banned"

            return dict(self._headers, **response_headers)

        def json(self) -> dict:
            import json

            return json.loads(self.text)

        @property
        def text(self) -> str:
            return self.content.decode("utf-8", errors="replace")  # type: ignore

        @property
        def url(self):
            return self._url

        @property
        def elapsed(self):
            return faker.time_delta()

        @property
        def request(self):
            request_headers = {}
            mock_request = mocker.MagicMock(spec=Request)
            mock_request_headers = mocker.PropertyMock(return_value=request_headers)
            type(mock_request).headers = mock_request_headers
            return mock_request

    def mockresponse_factory(data: dict, response_type, **kwargs) -> MockResponse:

        status_code = data.get("status_code", 200)
        content: bytes = data.get("content", b'{"test": "test"}')
        headers = data.get("headers", {"x-header": "test"})

        rv = MockResponse(
            response_type=response_type,
            content=content,
            status_code=status_code,
            headers=headers,
            **kwargs,
        )
        return rv

    def get_reviews_side_effect(*args, **kwargs):

        response_type = AirBnBResponseTypes.review

        try:
            response_data = response_queue.get_nowait()
        except ExcEmptyQueue as e:
            raise ExcEmptyQueue("Queue is empty. Did you forget to add entries with response_queue fixture?") from e
        response_queue.task_done()

        rv = mockresponse_factory(response_data, response_type, **kwargs)
        return rv

    def get_user_side_effect(*args, **kwargs):

        response_type = AirBnBResponseTypes.userDetail
        try:
            response_data = response_queue.get_nowait()
        except ExcEmptyQueue as e:
            raise ExcEmptyQueue("Queue is empty. Did you forget to add entries with response_queue fixture?") from e
        response_queue.task_done()

        rv = mockresponse_factory(response_data, response_type, **kwargs)
        return rv

    def get_calendar_side_effect(*args, **kwargs):

        try:
            response_data = response_queue.get_nowait()
        except ExcEmptyQueue as e:
            raise ExcEmptyQueue("Queue is empty. Did you forget to add entries with response_queue fixture?") from e
        response_queue.task_done()
        rv = mockresponse_factory(response_data, AirBnBResponseTypes.calendar, **kwargs)
        return rv

    # aka: search
    def get_homes_side_effect(*args, **kwargs):

        response_type = AirBnBResponseTypes.search

        try:
            response_data = response_queue.get_nowait()
        except ExcEmptyQueue as e:
            raise ExcEmptyQueue("Queue is empty. Did you forget to add entries with response_queue fixture?") from e
        response_queue.task_done()

        rv = mockresponse_factory(response_data, response_type, **kwargs)
        return rv

    def get_listing_details_side_effect(*args, **kwargs):
        try:
            response_data = response_queue.get_nowait()
        except ExcEmptyQueue as e:
            raise ExcEmptyQueue("Queue is empty. Did you forget to add entries with response_queue fixture?") from e
        response_queue.task_done()

        rv = mockresponse_factory(response_data, AirBnBResponseTypes.listingDetail, **kwargs)

        return rv

    m = mocker.patch("ubdc_airbnb.airbnb_interface.airbnb_api.AirbnbApi", autospec=True)
    m().get_homes.side_effect = get_homes_side_effect
    m().get_listing_details.side_effect = get_listing_details_side_effect
    m().get_calendar.side_effect = get_calendar_side_effect
    m().get_user.side_effect = get_user_side_effect
    m().get_reviews.side_effect = get_reviews_side_effect
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


@pytest.fixture()
def ubdctask_model(db):
    from django.apps import apps as django_apps

    model = django_apps.get_model("app.UBDCTask")
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
