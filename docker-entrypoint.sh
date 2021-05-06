#!/usr/bin/env bash
set -Eeo pipefail
CONCURRENCY=${WORKERS_PER_INSTANCE:-1}

if [[ -n "$1" ]]; then
  # if we start with a params assume we want to run that
  if [ "$1" = "migrate" ]; then
    echo "migrate"
    python ./dj_airbnb/manage.py migrate
    exit
  elif [ "$1" = "load-mask" ]; then
    echo "load-mask"
    if [ -n "$2" ]; then
      python ./dj_airbnb/manage.py import_world_mask --only-iso "$2"
    else
      python ./dj_airbnb/manage.py import_world_mask
    fi
    exit
  elif [ "$1" = "prep-grid" ]; then
    echo "prep-grid"
    python ./dj_airbnb/manage.py generate_grid "$2"
    exit
  elif [ "$1" = "send-task" ]; then
    python ./dj_airbnb/manage.py send_task "$2"
    exit
  elif [ "$1" = 'tidy-grids' ]; then
    python ./dj_airbnb/manage.py tidi_grid
    exit
  elif [ "$1" = 'shell' ]; then
    python ./dj_airbnb/manage.py shell
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
