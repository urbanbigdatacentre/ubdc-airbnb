#!/usr/bin/env bash
set -Eeo pipefail

case $1 in
migrate)
  ## Apply the migration scripts
  echo -n "migrate"
  python ./manage.py migrate
  ;;
load-mask)
  ## Load the world-mask. World mask prevents the generation of search-grids inside the oceasn
  echo -n "load-mask"
  python ./manage.py import_world_mask "${@:2}"
  ;;
tidy-grids)
  ##
  echo -n "tidy-grids"
  python ./manage.py tidy_grid
  ;;
sense-aoi)
  # Sence if there are more than the allowed listings on each grid inside the AOI
  echo "sense-aoi"
  python ./manage.py sense_aoi "${@:2}"
  ;;
prep-grid)
  # Create an initial grip for searching listing_ids.
  echo "prep-grid"
  python ./manage.py generate_grid "${@:2}"
  ;;

fetch-calendar)
  # Fetch the calendar for a listing_id
  echo "fetch-calendar"
  python ./manage.py fetch_resource_for_listing calendar "${@:2}"
  ;;
fetch-listing-detail)
  # Fetch listing-details for a listing_id
  echo "fetch-listing-detail"
  python ./manage.py fetch_resource_for_listing listing-detail "${@:2}"
  ;;
fetch-reviews)
  # fetch the reviews for a listing_id
  echo "fetch-reviews"
  python ./manage.py fetch_resource_for_listing reviews "${@:2}"
  ;;

sent-task)
  # sent one of the pre-defined tasks for execution
  python ./manage.py send_task "${@:2}"
  ;;
manage)
  python ./manage.py "${@:2}"
  ;;
start-worker)
  # Start a worker. The second argument declares the queue to be attached at.
  echo "!!!Starting Worker!!!"
  if [[ -z "$2" ]]; then
    echo "Starting Worker at default queue"
    celery -A core.celery:app worker -l info --concurrency=1
  else
    echo "Starting Worker at queue $2"
    celery -A core.celery:app worker -l info --concurrency=1 -Q $2
  fi
  ;;
start-beat)
  # start the beat process. Only one beat worker is needed in the system.
  echo "Starting Beat"
  celery -A core.celery:app beat -l info -s /celerybeat-schedule.d --pidfile="$(mktemp)".pid
  ;;
*)
  # default: Execute as is
  exec "$@"
  ;;
esac

# Exit with the previous exit code
exit $?
