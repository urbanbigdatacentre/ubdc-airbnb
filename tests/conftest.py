from datetime import timezone
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from faker import Faker

if TYPE_CHECKING:
    from typing import Annotated, ClassVar

    from django.db.models.query import QuerySet

    from ubdc_airbnb.models import AirBnBListing


fake = Faker()

UTC = timezone.utc


@pytest.fixture(scope="session")
def mock_airbnb_client(session_mocker):
    # from ubdc_airbnb.airbnb_interface import airbnb_api
    from collections import Counter

    from requests import Request, Response
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
            return f"http://test.com/?listing_id={self.listing_id}&param=2"

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

        # how any times this function has been called?
        # Ask the parent mock object.
        # Obviouslly, this is a hack and depents that this function is called from a mock object
        # get a ref to parent mock object
        mref = inspect.currentframe().f_back.f_locals.get("self")  # type: ignore
        # get the call count
        times_called: int = mref.call_count  # type: ignore

        # listing_ids starting with 8:
        # every odd call returns 503
        # every even call returns 200
        if str(listing_id).startswith("8"):
            if times_called % 2 == 1:
                # 503
                status_code = 503
                headers.update({"X-Crawlera-Error": "banned"})
                response = MockResponse(
                    status_code=status_code,
                    json_data={"test": "test"},
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
                    json_data={"test": "test"},
                    listing_id=listing_id,
                    headers=headers,
                    kwargs=kwargs,
                )
                return rv, rv.json()
        else:
            rv = MockResponse(
                status_code=status_code,
                json_data={"test": "test"},
                listing_id=listing_id,
                headers=headers,
                kwargs=kwargs,
            )

            return rv, rv.json()

    from ubdc_airbnb.airbnb_interface.airbnb_api import AirbnbApi

    m = session_mocker.patch.object(
        AirbnbApi,
        "get_calendar",
        side_effect=calendar_side_effect,
    )

    m.__name__ = "mock_get_calendar"

    return m


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
    from django.contrib.gis.db.models import Union
    from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
    from django.db.models import TextField
    from django.db.models.functions import Cast

    from ubdc_airbnb.models import AirBnBListing, AOIShape

    def create_aoi():

        # fmt: off
        recent_listings_aoi = (
            AirBnBListing
             .objects
             .annotate(as_str=Cast("listing_id", TextField()))
            .filter(as_str__startswith=7)
            .aggregate(geom=Union("geom_3857"))
        )['geom'].convex_hull
        stale_listings_aoi = (
            AirBnBListing
             .objects
             .annotate(as_str=Cast("listing_id", TextField()))
            .filter(as_str__startswith=8)
            .aggregate(geom=Union("geom_3857"))
        )['geom'].convex_hull

        new_listings_aoi = (
            AirBnBListing
             .objects
             .annotate(as_str=Cast("listing_id", TextField()))
            .filter(as_str__startswith=9)
            .aggregate(geom=Union("geom_3857"))
        )['geom'].convex_hull
        # fmt: on

        geometries = [
            recent_listings_aoi,
            stale_listings_aoi,
            new_listings_aoi,
        ]
        for idx, geom in enumerate(geometries, 1):
            AOIShape.objects.create(
                name=f"test-area-{idx}",
                geom_3857=MultiPolygon(geom, srid=3857),
                collect_bookings=True,
                collect_reviews=False,
                collect_calendars=True,
                collect_listing_details=True,
                scan_for_new_listings=True,
            )

    def create_listings():
        from django.contrib.gis.geos import GEOSGeometry

        from ubdc_airbnb.models import AirBnBListing

        geometries = [
            """{"coordinates": [-4.240,55.855],"type": "Point"}}""",
            """ {"coordinates": [-4.031,55.339],"type": "Point"}}""",
        ]

        NEW_LISTINGS = 10
        for idx in range(NEW_LISTINGS):
            PREFIX = "999999"
            lat, lon = fake.local_latlng(country_code="GB", coords_only=True)
            WKText = f'{{"coordinates": [{lon},{lat}],"type": "Point"}}}}'
            geom = GEOSGeometry(WKText)
            geom.srid = 4326
            geom.transform(3857)
            AirBnBListing.objects.create(
                listing_updated_at=None,
                calendar_updated_at=None,
                booking_quote_updated_at=None,
                reviews_updated_at=None,
                listing_id=int(PREFIX + str(idx)),
                geom_3857=geom,
            )

        STALE_LISTINGS = 10
        for idx in range(STALE_LISTINGS):
            PREFIX = "899999"
            lat, lon = fake.local_latlng(country_code="GB", coords_only=True)
            WKText = f'{{"coordinates": [{lon},{lat}],"type": "Point"}}}}'
            geom = GEOSGeometry(WKText)
            geom.srid = 4326
            geom.transform(3857)
            AirBnBListing.objects.create(
                listing_updated_at=fake.date_time_between(
                    start_date="-1y",
                    end_date="-1w",
                    tzinfo=UTC,
                ),
                calendar_updated_at=fake.date_time_between(
                    start_date="-1y",
                    end_date="-1w",
                    tzinfo=UTC,
                ),
                booking_quote_updated_at=fake.date_time_between(
                    start_date="-1y",
                    end_date="-1w",
                    tzinfo=UTC,
                ),
                reviews_updated_at=fake.date_time_between(
                    start_date="-1y",
                    end_date="-1w",
                    tzinfo=UTC,
                ),
                listing_id=int(PREFIX + str(idx)),
                geom_3857=geom,
            )

        RECENT_LISTINGS = 10
        for idx in range(STALE_LISTINGS):
            PREFIX = "799999"
            lat, lon = fake.local_latlng(country_code="GB", coords_only=True)
            WKText = f'{{"coordinates": [{lon},{lat}],"type": "Point"}}}}'
            geom = GEOSGeometry(WKText)
            geom.srid = 4326
            geom.transform(3857)
            AirBnBListing.objects.create(
                listing_updated_at=fake.date_time_between(
                    start_date="-1d",
                    tzinfo=UTC,
                ),
                calendar_updated_at=fake.date_time_between(
                    start_date="-1d",
                    tzinfo=UTC,
                ),
                booking_quote_updated_at=fake.date_time_between(
                    start_date="-1d",
                    tzinfo=UTC,
                ),
                reviews_updated_at=fake.date_time_between(
                    start_date="-1d",
                    tzinfo=UTC,
                ),
                listing_id=int(PREFIX + str(idx)),
                geom_3857=geom,
            )

    with django_db_blocker.unblock():
        create_listings()
        create_aoi()
        assert AirBnBListing.objects.count() == 30
        assert AOIShape.objects.count() == 3

    return


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
