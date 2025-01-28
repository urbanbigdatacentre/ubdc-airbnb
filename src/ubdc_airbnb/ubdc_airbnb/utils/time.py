from datetime import datetime, timedelta, timezone

UTC = timezone.utc


def start_of_day():
    return datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def seconds_from_now(seconds: int = 60 * 60 * 23):
    return datetime.now(UTC) + timedelta(seconds=seconds)


def end_of_day():
    return datetime.now(UTC).replace(hour=23, minute=59, second=59, microsecond=999999)
