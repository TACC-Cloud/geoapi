TAG := $(shell git log --format=%h -1)
GEOAPI_IMAGE=taccaci/geoapi
GEOAPI_WORKERS=taccaci/geoapi-workers

.PHONY: start
start:
	docker-compose -f devops/docker-compose.local.yml --env-file .env up

.PHONY: stop
stop:
	docker-compose -f devops/docker-compose.local.yml --env-file .env down

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

.PHONY: deploy-geoapi
deploy-geoapi:
	docker push $(GEOAPI_IMAGE):$(TAG)
	docker push $(GEOAPI_IMAGE):latest

.PHONY: deploy-workers
deploy-workers:
	docker push $(GEOAPI_WORKERS):$(TAG)
	docker push $(GEOAPI_WORKERS):latest
