#!/usr/bin/env bash
set -Eeo pipefail
CONCURRENCY=${WORKERS_PER_INSTANCE:-1}

if [[ -n "$1" ]]; then
  # if we start with a params assume we want to run
  if [ "$1" = "migrate" ]; then
    python ./dj_airbnb/manage.py migrate
    exit
  fi
  exec "$@"
fi

if
  [ "$MODE" = "worker" ]
then
  echo "!!!Starting Worker!!!"
  celery -A dj_airbnb.celery:app worker -l info --concurrency="${CONCURRENCY}"
  exit
elif
  [ "$MODE" = "beat" ]
then
  echo "Starting Beat"
  celery -A dj_airbnb.celery:app beat -l info -s /celerybeat-schedule.d --pidfile="$(mktemp)".pid
  exit
fi

exit $?
