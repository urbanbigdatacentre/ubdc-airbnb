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
  elif [ "$1" = "fetch-calendar" ]; then
    echo "fetch-calendar"
    python ./dj_airbnb/manage.py fetch_resource_for_listing calendar "$2"
    exit
  elif [ "$1" = "fetch-listing-detail" ]; then
    echo "fetch-listing-detail"
    python ./dj_airbnb/manage.py fetch_resource_for_listing listing-detail "$2"
    exit
  elif [ "$1" = "fetch-reviews" ]; then
    echo "fetch-reviews"
    python ./dj_airbnb/manage.py fetch_resource_for_listing reviews "$2"
    exit
  elif [ "$1" = "find-listings" ]; then
    echo "find-listings"
    python ./dj_airbnb/manage.py find_listings_aoi "$2"
    exit
  elif [ "$1" = "sense-aoi" ]; then
    echo "sense-aoi"
    python ./dj_airbnb/manage.py sense_aoi "$2"
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
