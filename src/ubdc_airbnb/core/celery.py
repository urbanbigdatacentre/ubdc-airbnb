import os
from typing import Any, Optional
from django.conf import settings

import django
from celery import Celery, Task
from celery.schedules import crontab
from celery.utils.log import get_task_logger

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

# localhost host,
#    default port,
#   user name guest,
#   password guest and
# virtual host “/”

app = Celery(
    'airbnb_app',
    task_cls='ubdc_airbnb.task_managers:BaseTaskWithRetry',
    broker=settings.CELERY_BROKER_URI,
    result_extended=True)
app.config_from_object(
    settings,
    namespace='CELERY',
    force=True)
app.autodiscover_tasks(force=True)
app.autodiscover_tasks(
    related_name='operations',
    force=True)

task_registry_copy = app.tasks.copy()
for k in task_registry_copy.keys():
    new_key = k.replace('ubdc_airbnb', 'app')
    app.tasks[new_key] = app.tasks[k]


app.conf.beat_schedule = {
    # 'add-every-monday-morning': {
    #     'task': 'ubdc_airbnb.celery.debug_task_wait',
    #     'schedule': crontab(),  # every minute
    #     'kwargs': {
    #         'value': 'DING!',
    #         "wait": 1
    #     },
    #     'options': {
    #         'expires': 10,
    #         'priority': 1
    #     }
    # },
    'op_update_listing_details_periodical': {
        'task': 'ubdc_airbnb.operations.listing_details.op_update_listing_details_periodical',
        'schedule': crontab(minute=0, hour='*/4'),  # At minute 0 past every 4th hour.
        'kwargs': {
            "how_many": 5000,
            "age_hours": 14 * 24
        },
        'options': {
            'priority': 4
        }
    },
    'op_update_reviews_periodical': {
        'task': 'ubdc_airbnb.operations.reviews.op_update_reviews_periodical',
        'schedule': crontab(minute=0, hour='*/4'),  # At minute 0 past every 4th hour.
        'kwargs': {
            "how_many": 1500,
            "age_hours": 14 * 24
        },
        'options': {
            'priority': 4
        }
    },
    'op_estimate_listings_or_divide_periodical': {
        'task': 'ubdc_airbnb.operations.grids.op_estimate_listings_or_divide_periodical',
        'schedule': crontab(minute=0, hour='*/4'),  # At minute 0 past every 4th hour.
        'kwargs': {
            "how_many": 500,
            "age_hours": 14 * 24,
            "max_listings": 50
        },
        'options': {
            'priority': 4
        }
    },
    'op_update_calendar_periodical': {
        'task': 'ubdc_airbnb.operations.calendars.op_update_calendar_periodical',
        'schedule': crontab(minute=0, hour='*/4'),  # At minute 0 past every 4th hour.
        'kwargs': {
            "how_many": 10000,
            "age_hours": 23,
            "priority": 5,
            "use_aoi": True
        },
        'options': {
            'priority': 5
        }
    },
    'op_discover_new_listings_periodical': {
        'task': 'ubdc_airbnb.operations.discovery.op_discover_new_listings_periodical',
        'schedule': crontab(minute=0, hour='*/4'),  # At minute 0 past every 4th hour.
        'kwargs': {
            "how_many": 500,
            "age_hours": 7 * 24,
            "use_aoi": True,
            "priority": 4
        },
        'options': {
            'priority': 4
        }
    },
    'op_tidy_grids': {
        'task': 'ubdc_airbnb.tasks.task_tidy_grids',
        'schedule': crontab(minute=0, hour=0, day_of_month=15),  # At 00:00 on day-of-month 15.
        'kwargs': {"less_than": 50},
        'options': {
            'priority': 3
        }
    },
}


@app.task(bind=True)
def debug_task_wait(self: Task, value=None, wait: int = 0) -> Optional[Any]:
    logger = get_task_logger(__name__)
    logger.info(f'\n'
                f'\tTask ID {self.request.id} was received.\n'
                f'\tThe name of this task is {self.name}\n'
                f'\tI will wait for {wait} seconds before returning with value: {value}.'
                f'\n')
    if wait > 0:
        import time
        print('I WORK')
        time.sleep(wait)

    return value
