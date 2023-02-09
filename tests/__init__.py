import logging
import re
import sys
from pathlib import Path
from typing import Iterable

import psycopg2
from celery.contrib.testing.app import TestApp
from celery.contrib.testing.worker import start_worker
from django.conf import settings
from django.test import TransactionTestCase, override_settings

from core import settings as settings_actual

fixtureBase = Path(__file__).parent / "testFixtures"

celery_app = TestApp(
    task_cls="ubdc_airbnb.task_managers:BaseTaskWithRetry", result_extended=True
)
celery_app.config_from_object(
    settings_actual, namespace="CELERY", force=True, silent=False
)
celery_app.autodiscover_tasks(force=True)
celery_app.autodiscover_tasks(related_name="operations", force=True)


def get_fixture(fixture_name: str, as_posisx=True):
    if as_posisx:
        return fixtureBase.joinpath(fixture_name).as_posix()
    else:
        return fixtureBase.joinpath(fixture_name)


class UBDCBaseTest(TransactionTestCase):
    sql_fixtures = None
    reset_sequences = False
    project_root = settings.BASE_DIR
    db_settings = settings.DATABASES["default"]
    uuid_regex = re.compile(
        r"[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}"
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
        if cls.sql_fixtures and not isinstance(cls.sql_fixtures, str):
            if cls.fixtures:
                raise ValueError("no sql and fixtures together")

            for sql_fixture in cls.sql_fixtures:
                with open(sql_fixture, "r", encoding="utf8") as fh:
                    conn = psycopg2.connect(
                        f"dbname = '{cls.db_settings['NAME']}' "
                        f"user = '{cls.db_settings['USER']}' "
                        f"host = '{cls.db_settings['HOST']}' "
                        f"password='{cls.db_settings['PASSWORD']}'"
                    )
                    cur = conn.cursor()
                    cur.execute(fh.read())
                    conn.commit()


@override_settings(CELERY_BROKER_URI="amqp://rabbit:carrot@localhost:5672//")
class UBDCBaseTestWorker(UBDCBaseTest):
    celery_worker_perform_ping_check = False
    celery_worker: Iterable

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Start up celery worker
        cls.celery_worker = start_worker(
            celery_app,
            pool="solo",
            concurrency=1,
            perform_ping_check=cls.celery_worker_perform_ping_check,
        )
        cls.celery_worker.__enter__()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        # Close worker
        cls.celery_worker.__exit__(None, None, None)
