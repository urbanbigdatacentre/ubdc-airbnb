COMMIT := $(shell git rev-parse --short HEAD)
PROJECT_NAME := ubdc-airbnb
PWD := $(shell pwd)/src/ubdc_airbnb

build-image:
	docker build  -t ubdc/$(PROJECT_NAME):$(COMMIT) .

push-image: build-image
	docker push ubdc/$(PROJECT_NAME):$(COMMIT)

make-migrations: build-image
	docker run -it --rm -v $(PWD):/app --env-file .env.prod --entrypoint bash ubdc/$(PROJECT_NAME):$(COMMIT) -c "cd /app && python manage.py makemigrations"

start-dev-gen-worker: build-image
	docker run -it --rm -v $(PWD):/app --env-file .env.dev  ubdc/$(PROJECT_NAME):$(COMMIT) start-worker

start-dev-cal-worker: build-image
	docker run -it --rm -v $(PWD):/app --env-file .env.dev --entrypoint bash ubdc/$(PROJECT_NAME):$(COMMIT) -c "celery -A core.celery:app worker -l info --concurrency=1 -Q calendar"
