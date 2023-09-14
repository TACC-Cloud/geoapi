TAG := $(shell git log --format=%h -1)
GEOAPI_IMAGE=taccaci/geoapi
GEOAPI_WORKERS=taccaci/geoapi-workers

.PHONY: geoapi
geoapi:
	docker build -t $(GEOAPI_IMAGE):$(TAG) -f devops/Dockerfile .
	docker tag $(GEOAPI_IMAGE):$(TAG) $(GEOAPI_IMAGE):latest

.PHONY: workers
workers:
	docker build -t $(GEOAPI_WORKERS):$(TAG) -f devops/Dockerfile.potree .
	docker tag $(GEOAPI_WORKERS):$(TAG) $(GEOAPI_WORKERS):latest

.PHONY: deploy-geoapi
deploy-geoapi:
	docker push $(GEOAPI_IMAGE):$(TAG)
	docker push $(GEOAPI_IMAGE):latest

.PHONY: deploy-workers
deploy-workers:
	docker push $(GEOAPI_WORKERS):$(TAG)
	docker push $(GEOAPI_WORKERS):latest
