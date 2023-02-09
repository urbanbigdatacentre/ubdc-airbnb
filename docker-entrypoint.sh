#!/usr/bin/env bash
set -Eeo pipefail

case $1 in
migrate)
  echo -n "migrate"
  python ./manage.py migrate
  ;;
load-mask)
  echo -n "load-mask"
  python ./manage.py import_world_mask "${@:2}"
  ;;
tidy-grids)
  echo -n "tidy-grids"
  python ./manage.py tidy_grid
  ;;
sense-aoi)
  echo "sense-aoi"
  python ./manage.py sense_aoi "${@:2}"
  ;;
prep-grid)
  echo "prep-grid"
  python ./manage.py generate_grid "${@:2}"
  ;;

fetch-calendar)
  echo "fetch-calendar"
  python ./manage.py fetch_resource_for_listing calendar "${@:2}"
  ;;
fetch-listing-detail)
  echo "fetch-listing-detail"
  python ./manage.py fetch_resource_for_listing listing-detail "${@:2}"
  ;;
fetch-reviews)
  echo "fetch-reviews"
  python ./manage.py fetch_resource_for_listing reviews "${@:2}"
  ;;

sent-task)
  python ./manage.py send_task "${@:2}"
  ;;
manage)
  python ./manage.py "${@:2}"
  ;;
start-worker)
  echo "!!!Starting Worker!!!"
  celery -A core.celery:app worker -l info --concurrency=1
  ;;
start-beat)
  echo "Starting Beat"
  celery -A core.celery:app beat -l info -s /celerybeat-schedule.d --pidfile="$(mktemp)".pid
  ;;
*)
  exec "$@"
  ;;
esac
exit $?
