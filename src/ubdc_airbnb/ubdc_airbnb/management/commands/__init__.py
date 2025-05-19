from django.core.management import CommandError

from ubdc_airbnb.models import AirBnBListing, AOIShape


def int_to_aoi(value) -> AOIShape:
    """
    Cast to AOI Object
    """
    try:
        return AOIShape.objects.get(pk=value)
    except AOIShape.DoesNotExist:
        raise CommandError(f"AOI with primary key {value} does not exist.")


def int_to_listing(value) -> AirBnBListing:
    """
    Cast to AirBnBListing Object
    """
    try:
        listing = AirBnBListing.objects.get(listing_id=value)
    except AirBnBListing.DoesNotExist:
        raise CommandError(f"Listing with ID {value} does not exist.")
    return listing


def get_beat_tasks():
    """
    Return a list of all task names in the beat schedule.
    """
    from core.celery import app

    beat_entries: dict = app.conf.beat_schedule

    jobs = list(x.split(".")[-1] for x in beat_entries.keys())

    return jobs


def get_beat_task_by_name(task_name: str):
    """
    Return the task object for a given task name. \n
    Task names can be retrieved using get_beat_tasks()
    """

    import importlib

    from core.celery import app

    beat_entries: dict = app.conf.beat_schedule
    candidates = [key for key in beat_entries.keys() if key.endswith(task_name)]
    if len(candidates) != 1:
        raise ValueError(f"Expected exactly one task ending with '{task_name}', found {len(candidates)}")

    entry = beat_entries[candidates[0]]
    task_fqn = entry["task"]
    task_module_str = task_fqn.rsplit(".", 1)[0]
    task_str = task_fqn.split(".")[-1]

    module_symbol = importlib.import_module(task_module_str)
    job_obj = getattr(module_symbol, task_str)

    return job_obj
