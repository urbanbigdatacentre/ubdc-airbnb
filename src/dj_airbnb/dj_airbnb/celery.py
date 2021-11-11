import os
import django
from typing import Any, Optional, Dict, Union, Tuple
from celery import Celery, Task
from celery.schedules import crontab
from celery.utils.log import get_task_logger

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dj_airbnb.settings')
django.setup()

# localhost host,
#    default port,
#   user name guest,
#   password guest and
# virtual host “/”

# amqp://guest:guest@localhost:5672//
CELERY_BROKER_URI = \
    'pyamqp://{rabbit_username}:{rabbit_password}@{rabbit_host}:{rabbit_port}/{rabbit_virtual_host}'.format(
        rabbit_username=os.getenv("RABBITMQ_USERNAME", 'rabbit'),
        rabbit_password=os.getenv("RABBITMQ_PASSWORD", 'carrot'),
        rabbit_host=os.getenv("RABBITMQ_HOST", 'localhost'),
        rabbit_port=os.getenv("RABBITMQ_PORT", 5672),
        rabbit_virtual_host=os.getenv("RABBITMQ_VIRTUAL_HOST", "/")
    )
print(CELERY_BROKER_URI)

app = Celery('airbnb_app', task_cls='app.task_managers:BaseTaskWithRetry', broker=CELERY_BROKER_URI,
             result_extended=True)
app.config_from_object('django.conf:settings', namespace='CELERY', force=True)

app.autodiscover_tasks(force=True)
app.autodiscover_tasks(related_name='operations', force=True)

app.conf.beat_schedule = {
    # 'add-every-monday-morning': {
    #     'task': 'dj_airbnb.celery.debug_task_wait',
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
        'task': 'app.operations.listing_details.op_update_listing_details_periodical',
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
        'task': 'app.operations.reviews.op_update_reviews_periodical',
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
        'task': 'app.operations.grids.op_estimate_listings_or_divide_periodical',
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
        'task': 'app.operations.calendars.op_update_calendar_periodical',
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
        'task': 'app.operations.discovery.op_discover_new_listings_periodical',
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
        'task': 'app.tasks.task_tidy_grids',
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
