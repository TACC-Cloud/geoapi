TAG := $(shell git log --format=%h -1)
GEOAPI_IMAGE=taccaci/geoapi
GEOAPI_WORKERS=taccaci/geoapi-workers

.PHONY: start
start:
	docker-compose -f devops/docker-compose.local.yml --env-file .env up

.PHONY: stop
stop:
	docker-compose -f devops/docker-compose.local.yml --env-file .env down

.PHONY: restart-workers
restart-workers:  ## Restart workers
	docker-compose -f devops/docker-compose.local.yml --env-file .env restart workers

.PHONY: build
build:
	make geoapi && make workers

.PHONY: geoapi
geoapi:
	docker build -t $(GEOAPI_IMAGE):$(TAG) -f devops/Dockerfile .
	docker tag $(GEOAPI_IMAGE):$(TAG) $(GEOAPI_IMAGE):latest
	docker tag $(GEOAPI_IMAGE):$(TAG) $(GEOAPI_IMAGE):local

.PHONY: workers
workers:
	docker build -t $(GEOAPI_WORKERS):$(TAG) -f devops/Dockerfile.worker .
	docker tag $(GEOAPI_WORKERS):$(TAG) $(GEOAPI_WORKERS):latest
	docker tag $(GEOAPI_WORKERS):$(TAG) $(GEOAPI_WORKERS):local


.PHONY: deploy
deploy:
	make deploy-geoapi && make deploy-workers

.PHONY: deploy-geoapi
deploy-geoapi:
	docker push $(GEOAPI_IMAGE):$(TAG)
	docker push $(GEOAPI_IMAGE):latest

.PHONY: deploy-workers
deploy-workers:
	docker push $(GEOAPI_WORKERS):$(TAG)
	docker push $(GEOAPI_WORKERS):latest

.PHONY: help
help:  ## Display this help screen
	@grep -E '^([a-zA-Z_-]+):.*?## .*$$|^([a-zA-Z_-]+):' $(MAKEFILE_LIST) \
	| awk 'BEGIN {FS = ":.*?## "}; {if ($$2) {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2} else {printf "\033[36m%-30s\033[0m %s\n", $$1, "(no description)"}}'
