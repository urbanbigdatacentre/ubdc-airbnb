COMMIT := $(shell git rev-parse --short HEAD)
PROJECT_NAME := ubdc-airbnb
PWD := $(shell pwd)/src/ubdc_airbnb

build-image:
	docker build -t ubdc/$(PROJECT_NAME):$(COMMIT) .

make-migrations: build-image
	docker run -it --rm -v $(PWD):/app --env-file .env.prod --entrypoint bash ubdc/$(PROJECT_NAME):$(COMMIT) -c "cd /app && python manage.py makemigrations"
