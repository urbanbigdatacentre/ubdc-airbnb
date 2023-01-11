import inspect

from celery import signals
from celery.app.task import Context
from celery.utils.log import get_task_logger
from django.utils.datetime_safe import datetime

from app.models import UBDCTask, UBDCGroupTask

logger = get_task_logger(__name__)


@signals.before_task_publish.connect
def ubdc_handles_task_publish(sender: str = None, headers=None, body=None, **kwargs):
    """ Essential procedures after a task was published on the broker.
    This function is connected to the  after_task_publish signal """

    # filter messages (=function names)  that don't start with ubdc or core
    if not (sender.startswith('app') or
            sender.startswith('ubdc_airbnb')):
        return
    info = headers

    task_id = info['id']
    group_task_id = info.get('group', None)
    root_id = None if task_id == info.get('root_id') else info.get('root_id', task_id)
    if group_task_id:
        group_task_obj, created = UBDCGroupTask.objects.get_or_create(group_task_id=group_task_id, root_id=root_id)

    else:
        group_task_obj = None
    # in case of Retry, celery will try to
    # republish the task with the same task_id
    # _kwargs_repr = json.dumps(body[1])

    task_obj, created = UBDCTask.objects.get_or_create(task_id=task_id)

    if created:
        _data = dict()
        _data.update(task_name=info['task'],
                     task_args=info['argsrepr'],
                     task_kwargs=body[1],
                     parent_id=info['parent_id'],
                     root_id=info['root_id'],
                     group_task=group_task_obj
                     )
        for k, v in _data.items():
            setattr(task_obj, k, v)
        task_obj.save()
        logger.info(f'{inspect.stack()[0][3]}: Created task: {info["id"]}')
    else:
        logger.info(f'{inspect.stack()[0][3]}: Task {info["id"]} found.')
    return


@signals.task_revoked.connect
def ubdc_handles_task_revoke(sender, expired: bool, request: Context, terminated: bool, **kwargs):
    task_name: str = sender.name

    task_id: str = request.id
    parent_id: str = request.parent_id
    root_id: str = request.root_id
    group_id: str = request.group

    if not (task_name.startswith('app') or task_name.startswith('ubdc_airbnb')):
        return

    this_task = UBDCTask.objects.get(task_id=task_id)
    this_task.status = UBDCTask.TaskTypeChoices.REVOKED
    this_task.datetime_finished = datetime.now()
    this_task.save()

    logger.info(f'Task: {task_id} have been successfully revoked')
