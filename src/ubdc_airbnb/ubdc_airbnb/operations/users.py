from typing import TYPE_CHECKING, List, Optional, Sequence, Union

from celery import group, shared_task
from celery.result import GroupResult

from ubdc_airbnb.tasks import task_update_user_details


@shared_task
def op_get_users_details(user_id: Union[int, Sequence[int]]) -> str:
    # TODO: FINISH
    if isinstance(user_id, Sequence):
        _user_ids = user_id
    else:
        _user_ids = (user_id,)

    job = group()
