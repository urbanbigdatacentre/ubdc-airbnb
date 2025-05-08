COMMIT := $(shell git rev-parse --short HEAD)
PROJECT_NAME := ubdc-airbnb
PWD := $(shell pwd)/src/ubdc_airbnb
.DEFAULT_GOAL := help
.PHONY: help
help: 
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m\033[0m\n"} /^[$$()% a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)


build-image: ## Build the docker image  
	docker build  -t ubdc/$(PROJECT_NAME):$(COMMIT) .

push-image: build-image ## Push the docker image to the registry
	docker push ubdc/$(PROJECT_NAME):$(COMMIT)

make-migrations: build-image ## Make django migrations
	docker run -it --rm -v $(PWD):/app --env-file .env.prod --entrypoint bash ubdc/$(PROJECT_NAME):$(COMMIT) -c "cd /app && python manage.py makemigrations"

start-dev-gen-worker: build-image ## Start a dev worker
	docker run -it --rm -v $(PWD):/app --env-file .env.dev  ubdc/$(PROJECT_NAME):$(COMMIT) start-worker

start-dev-cal-worker: build-image ## Start a dev calendar worker
	docker run -it --rm -v $(PWD):/app --env-file .env.dev --entrypoint bash ubdc/$(PROJECT_NAME):$(COMMIT) -c "celery -A core.celery:app worker -l info --concurrency=1 -Q calendar"

test:  ## Run tests
	poetry run pytest
	
format: ## Format code
	poetry run black src/ tests/
	poetry run isort src/ tests/

run-gh-action: ## Run GitHub action
	gh act pull_request 

