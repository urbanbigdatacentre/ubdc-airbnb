#!/usr/bin/env bash
set -Eeo pipefail
CONCURRENCY=${WORKER_CONCURRENCY:-1}
if
  [ "$MODE" = "worker" ]
then
  echo $ENV
  echo "Starting Worker"

  celery -A dj_airbnb.celery:app worker -l info --concurrency="$CONCURRENCY"
elif
  [ "$MODE" = "beat" ]
then
  echo "Starting Beat"
  celery -A dj_airbnb.celery:app beat -l info -s /celerybeat-schedule.d --pidfile="$(mktemp)".pid
fi

exit $?
