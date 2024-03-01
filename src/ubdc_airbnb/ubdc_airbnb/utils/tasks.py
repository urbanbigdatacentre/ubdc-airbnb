from datetime import timedelta
from typing import TYPE_CHECKING, Literal

from django.db.models import BigIntegerField
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast
from django.utils.timezone import now

from ubdc_airbnb.models import UBDCTask

if TYPE_CHECKING:
    from django.db.models import QuerySet


def get_submitted_listing_ids_for(
    purpose: Literal[
        "reviews",
        "listing_details",
        "calendars",
    ],
    exclude_submitted=False,
) -> "QuerySet[UBDCTask]":
    """Get a Queryset with all the listing_ids that were used in a task in the last 24hours"""
    match purpose:
        case "reviews":
            from ubdc_airbnb.tasks import task_add_listing_detail as task
        case "listing_details":
            from ubdc_airbnb.tasks import task_add_listing_detail as task
        case "calendars":
            from ubdc_airbnb.tasks import task_update_calendar as task
        case _:
            raise NotImplementedError()

    task_name = task.name
    timestamp_threshold = now() - timedelta(days=1)

    qs = (
        UBDCTask.objects.filter(datetime_submitted__gte=timestamp_threshold)
        .filter(task_kwargs__has_key="listing_id")
        .filter(task_name=task_name)
        # extract the listing_id from the task_kwargs param
        .annotate(
            listing_id=Cast(
                KeyTextTransform("listing_id", "task_kwargs"),
                BigIntegerField(),
            )
        )
    )

    # default
    if exclude_submitted:
        return qs.exclude(status=UBDCTask.TaskTypeChoices.SUBMITTED)

    qs = qs.order_by("listing_id").distinct("listing_id")

    return qs
