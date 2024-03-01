# import logging
# import re
# import sys
# from pathlib import Path
# from typing import Iterable

# import psycopg
# from celery.contrib.testing.app import TestApp
# from celery.contrib.testing.worker import start_worker
# from django.conf import settings
# from django.test import TransactionTestCase, override_settings

# from core import settings as settings_actual

# logger = logging.getLogger(__name__)

# fixtureBase = Path(__file__).parent / "testFixtures"

# celery_app = TestApp(task_cls="ubdc_airbnb.task_managers:BaseTaskWithRetry", result_extended=True)
# celery_app.config_from_object(settings_actual, namespace="CELERY", force=True, silent=False)
# celery_app.autodiscover_tasks(force=True)
# celery_app.autodiscover_tasks(related_name="operations", force=True)


# def get_fixture(fixture_name: str, as_posisx=True):
#     if as_posisx:
#         return fixtureBase.joinpath(fixture_name).as_posix()
#     else:
#         return fixtureBase.joinpath(fixture_name)


# class UBDCBaseTest(TransactionTestCase):
#     sql_fixtures = None
#     reset_sequences = False
#     project_root = settings.BASE_DIR
#     db_settings = settings.DATABASES["default"]
#     uuid_regex = re.compile(r"[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}")

#     @classmethod
#     def setUpClass(cls):
#         super().setUpClass()
#         logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
#         if cls.sql_fixtures and not isinstance(cls.sql_fixtures, str):
#             if cls.fixtures:
#                 raise ValueError("no sql and fixtures together")

#             for sql_fixture in cls.sql_fixtures:
#                 with open(sql_fixture, "r", encoding="utf8") as fh:
#                     conn = psycopg.connect(
#                         f"dbname = '{cls.db_settings['NAME']}' "
#                         f"user = '{cls.db_settings['USER']}' "
#                         f"host = '{cls.db_settings['HOST']}' "
#                         f"password='{cls.db_settings['PASSWORD']}'"
#                     )
#                     cur = conn.cursor()
#                     cur.execute(fh.read())
#                     conn.commit()

#     @classmethod
#     def tearDownClass(cls):
#         # purge all queues after each test
#         queues = celery_app.amqp.queues.keys()
#         qnum = len(queues)
#         if queues:
#             queues_headline = text.pluralize(qnum, "queue")

#             def _purge(conn, queue):
#                 try:
#                     return conn.default_channel.queue_purge(queue) or 0
#                 except conn.channel_errors:
#                     return 0

#             with celery_app.connection_for_write() as conn:
#                 messages = sum(_purge(conn, queue) for queue in queues)
#                 if messages:
#                     messages_headline = text.pluralize(messages, "message")
#                     logger.info(f"Purged {messages} {messages_headline} from " f"{qnum} known task {queues_headline}.")
#                 else:
#                     logger.info(f"No messages purged from {qnum} {queues_headline}.")


# @override_settings(CELERY_BROKER_URI="amqp://rabbitmq:rabbitmq@localhost:5672//")
# class UBDCBaseTestWorker(UBDCBaseTest):
#     celery_worker_perform_ping_check = False
#     celery_worker: Iterable

#     @classmethod
#     def setUpClass(cls):
#         print("Starting worker")
#         super().setUpClass()

#         # Start up celery worker
#         cls.celery_worker = start_worker(
#             celery_app,
#             pool="solo",
#             concurrency=1,
#             perform_ping_check=cls.celery_worker_perform_ping_check,
#         )
#         cls.celery_worker.__enter__()

#     @classmethod
#     def tearDownClass(cls):
#         # Close worker
#         cls.celery_worker.__exit__(None, None, None)
#         super().tearDownClass()
