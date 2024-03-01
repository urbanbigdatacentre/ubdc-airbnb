COMMIT := $(shell git rev-parse --short HEAD)
PROJECT_NAME := ubdc-airbnb

build-image:
	docker build -t ubdc/$(PROJECT_NAME):$(COMMIT) .
