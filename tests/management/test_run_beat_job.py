import warnings
from io import StringIO

import pytest
from django.core.management import call_command

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
    [
        "op_update_listing_details_periodical",
        "op_update_calendar_periodical",
        "op_discover_new_listings_periodical",
    ],
)
@pytest.mark.parametrize('args', [
    None,
    '--arg',
    '--arg=arg1=val1',
    '--arg=arg1=val1 --arg=arg2=val2'
])
def test_run_beat_job(mocker, job_name, args):
    from celery.app.task import Task

    m_sig = mocker.patch.object(Task, "s")
    # m_sig.id.return_value = "test-id"
    # m_job = m_sig.apply_async()

    from django.core.management import call_command

    out = StringIO()
    if args is None:
        call_command("run-beat-job", job_name, stdout=out)
    else:
        call_command("run-beat-job", job_name, *args.split(' '), stdout=out)

    # Checking the kwargs works but no tests
    assert m_sig().mock_calls[0][0] == "apply_async"
    assert m_sig().mock_calls[1][0] == "apply_async().id.__str__"

    out.seek(0)
    captured_out = out.read()

    assert len(captured_out) > 0
    assert "Sent Celery Beat Task"
