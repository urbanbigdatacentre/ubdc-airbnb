import os
from typing import Any, Optional

import django
from celery import Celery, Task
from celery.schedules import crontab
from celery.utils.log import get_task_logger
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

# Tasks with be routed according to the following.
# All other tasks will be routed to the default queue.
task_routes = {
    "ubdc_airbnb.tasks.task_update_calendar": {"queue": "calendar"},
}


app = Celery(
    main="airbnb_app",
    task_cls="ubdc_airbnb.task_managers:BaseTaskWithRetry",
    broker=settings.CELERY_BROKER_URI,
    backend=settings.RESULT_BACKEND,
    result_extended=True,
)
app.config_from_object(settings, namespace="CELERY", force=True)
# app.autodiscover_tasks(force=True)
# app.autodiscover_tasks(related_name="operations", force=True)
app.conf.task_routes = task_routes
app.conf.broker_connection_retry_on_startup = False


app.conf.beat_schedule = {
    # TODO: Remove priority from all tasks
    "op_update_listing_details_periodical": {
        "task": "ubdc_airbnb.operations.listing_details.op_update_listing_details_periodical",
        "schedule": crontab(minute=0, hour="*/2"),  # At minute 0 past every 4th hour.
        "kwargs": {"how_many": 5000, "age_hours": 14 * 24},
        "options": {"priority": 4},
    },
    "op_update_reviews_periodical": {
        "task": "ubdc_airbnb.operations.reviews.op_update_reviews_periodical",
        "schedule": crontab(minute=0, hour="*/3"),  # At minute 0 past every 4th hour.
        "kwargs": {"how_many": 1500, "age_hours": 14 * 24},
        "options": {"priority": 4},
    },
    "op_update_calendar_periodical": {
        "task": "ubdc_airbnb.operations.calendars.op_update_calendar_periodical",
        "schedule": crontab(minute=0, hour="2"),  # Every day at two in the morning.
        "kwargs": {"use_aoi": True},
    },
    "op_estimate_listings_or_divide_periodical": {
        "task": "ubdc_airbnb.operations.grids.op_estimate_listings_or_divide_periodical",
        "schedule": crontab(minute=0, hour="*/2"),  # At minute 0 past every 4th hour.
        "kwargs": {"how_many": 500, "age_hours": 14 * 24, "max_listings": 50},
        "options": {"priority": 4},
    },
    "op_discover_new_listings_periodical": {
        "task": "ubdc_airbnb.operations.discovery.op_discover_new_listings_periodical",
        "schedule": crontab(minute=0, hour="*/2"),  # At minute 0 past every 4th hour.
        "kwargs": {
            "how_many": 500,
            "age_hours": 7 * 24,
            "use_aoi": True,
            "priority": 4,
        },
        "options": {"priority": 4},
    },
    "op_tidy_grids": {
        "task": "ubdc_airbnb.tasks.task_tidy_grids",
        "schedule": crontab(minute=0, hour=0, day_of_month=15),  # At 00:00 on day-of-month 15.
        "kwargs": {"less_than": 50},
        "options": {"priority": 3},
    },
}


@app.task(bind=True)
def debug_task_wait(self: Task, value=None, wait: int = 0) -> Optional[Any]:
    logger = get_task_logger(__name__)
    logger.info(f"I will wait for {wait} seconds before returning with value: {value}.")
    if wait > 0:
        import time

        logger.info("I WORK")
        time.sleep(wait)
        logger.info("I AM DONE")

    return value
