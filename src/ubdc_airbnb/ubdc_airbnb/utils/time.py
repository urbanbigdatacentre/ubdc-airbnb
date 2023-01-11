from datetime import datetime, timedelta
from pytz import UTC


def seconds_later_from_now(seconds: int = 60 * 60 * 23):
    return datetime.now(UTC) + timedelta(seconds=seconds)
