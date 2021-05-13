TAG := $(shell git log --format=%h -1)
GEOAPI_IMAGE=taccaci/geoapi
GEOAPI_WORKERS=taccaci/geoapi-workers

.PHONY: geoapi
geoapi:
	docker build -t $(GEOAPI_IMAGE):$(TAG) .

.PHONY: workers
workers:
	docker build -t $(GEOAPI_WORKERS):$(TAG) -f Dockerfile.potree .

.PHONY: deploy-geoapi
deploy-geoapi:
	docker push $(GEOAPI_IMAGE):$(TAG)

.PHONY: deploy-workers
deploy-workers:
	docker push $(GEOAPI_WORKERS):$(TAG)
