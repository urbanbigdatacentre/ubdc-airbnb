import warnings
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

BEAT_EXPECTED_NUMBER_OF_ENTRIES = 4


def test_get_beat_entries():

    from ubdc_airbnb.management.commands import get_beat_tasks

    entries = get_beat_tasks()
    assert len(entries) > 0
    if len(entries) != BEAT_EXPECTED_NUMBER_OF_ENTRIES:
        warnings.warn(
            f"Expected {BEAT_EXPECTED_NUMBER_OF_ENTRIES} entries, but found {len(entries)}. Is a scheduled job missing?"
        )


@pytest.mark.parametrize(
    "job_name",
    argvalues=[
        "op_update_listing_details_periodical",
        "op_update_calendar_periodical",
        "op_discover_new_listings_periodical",
    ],
    ids=["listing_details", "calendar", "discover_new_listings"],
)
@pytest.mark.parametrize("args", [None, "--arg", "--arg=arg1=val1", "--arg=arg1=val1 --arg=arg2=val2"])
def test_run_beat_job(mocker, job_name, args, capsys):
    from celery.app.task import Task

    mock_s = mocker.patch.object(Task, "s")

    from django.core.management import call_command

    arg_list = args.split() if args else []

    call_command("run-beat-job", job_name, *arg_list)
    out, err = capsys.readouterr()

    # Checking the kwargs works but no tests
    assert mock_s().mock_calls[0][0] == "apply_async"
    assert mock_s().mock_calls[1][0] == "apply_async().id.__str__"
    for arg in arg_list:
        if "=" in arg:
            _, k, v = arg.split("=")
            assert k in mock_s.call_args_list[0].kwargs
            assert mock_s.call_args_list[0].kwargs[k] == v

    assert job_name in out
    assert "Sent Celery Beat Task"
