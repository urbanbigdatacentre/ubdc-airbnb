import logging
import queue
import types

import pytest
from celery.contrib.testing.worker import start_worker


def pytest_configure():
    from celery.fixups.django import DjangoWorkerFixup
    # DjangoWorkerFixup.on_worker_process_init = lambda x: None
    # DjangoWorkerFixup.close_database = lambda x: None

    DjangoWorkerFixup.install = lambda x: None


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    def create_aoi():
        from ubdc_airbnb.models import AOIShape
        from django.contrib.gis.geos import GEOSGeometry

        geometries = [
            """{ "type": "MultiPolygon", "coordinates": [[[[-4.5, 55.973 ], [ -4.5, 55.718 ], [ -3.882, 55.718 ], [ -3.882, 55.973 ], [-4.5, 55.973]]]]}""",
            """{ "type": "MultiPolygon", "coordinates": [[[[ -3.235, 55.952 ], [ -3.235, 55.924 ], [ -3.152, 55.924 ], [ -3.152, 55.952 ], [ -3.235, 55.952 ]]]]}""",
        ]

        for idx, g in enumerate(geometries, 1):
            geom = GEOSGeometry(g)
            geom.srid = 4326
            geom.transform(3857)
            AOIShape.objects.create(
                name=f"test-area-{idx}",
                geom_3857=geom,
                collect_bookings=idx % 2,
                collect_reviews=False,
                collect_calendars=idx % 2,
                collect_listing_details=idx % 2,
                scan_for_new_listings=idx % 2,
            )

    def create_listings():
        from ubdc_airbnb.models import AirBnBListing
        from django.contrib.gis.geos import GEOSGeometry

        geometries = [
            """{"coordinates": [-4.240,55.855],"type": "Point"}}""",
            """ {"coordinates": [-4.031,55.339],"type": "Point"}}""",
        ]
        for idx, g in enumerate(geometries):
            geom = GEOSGeometry(g)
            geom.srid = 4326
            geom.transform(3857)
            p = AirBnBListing.objects.create(listing_id=99999 + idx, geom_3857=geom)

    with django_db_blocker.unblock():
        create_aoi()
        create_listings()

    return

@pytest.fixture()
def listing_model(db):
    from django.apps import apps as django_apps

    return django_apps.get_model("app.AirBnBListing")

@pytest.fixture(scope='session')
def celery_worker_pool():
    return 'prefork'

@pytest.fixture(scope="function")
def celery_app(celery_app):
    # use our own celery app, which should be configured using the .env.test settings
    from core.celery import app as celery_app
    from celery.utils import text

    # with django_db_blocker.unblock():
    yield celery_app

    queues = celery_app.amqp.queues.keys()
    qnum = len(queues)
    if queues:
        queues_headline = text.pluralize(qnum, "queue")

        def _purge(conn, queue):
            try:
                return conn.default_channel.queue_purge(queue) or 0
            except conn.channel_errors:
                return 0

        with celery_app.connection_for_write() as conn:
            messages = sum(_purge(conn, queue) for queue in queues)
            if messages:
                messages_headline = text.pluralize(messages, "message")
                print(
                    f"Purged {messages} {messages_headline} from "
                    f"{qnum} known task {queues_headline}."
                )
            else:
                print(f"No messages purged from {qnum} {queues_headline}.")
