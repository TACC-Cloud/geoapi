TAG := $(shell git log --format=%h -1)
GEOAPI_IMAGE=taccwma/geoapi
GEOAPI_WORKERS=taccwma/geoapi-workers


####
# `DOCKER_IMAGE_BRANCH_TAG` tag is the git tag for the commit if it exists, else the branch on which the commit exists
# Note: Special chars are replaced with dashes, e.g. feature/some-feature -> feature-some-feature
DOCKER_IMAGE_BRANCH_TAG := $(shell git describe --exact-match --tags 2> /dev/null || git symbolic-ref --short HEAD | sed 's/[^[:alnum:]\.\_\-]/-/g')



.PHONY: help
help:  ## Display this help screen
	@grep -E '^([a-zA-Z_-]+):.*?## .*$$|^([a-zA-Z_-]+):' $(MAKEFILE_LIST) \
	| awk 'BEGIN {FS = ":.*?## "}; {if ($$2) {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2} else {printf "\033[36m%-30s\033[0m %s\n", $$1, "(no description)"}}'

.PHONY: start
start:
	docker compose -f devops/docker-compose.local.yml --env-file .env up

.PHONY: stop
stop:
	docker compose -f devops/docker-compose.local.yml --env-file .env down

.PHONY: restart-workers
restart-workers:  ## Restart workers
	docker compose -f devops/docker-compose.local.yml --env-file .env restart workers workers-heavy

.PHONY: restart-nginx
restart-nginx:  ## Restart nginx
	docker compose -f devops/docker-compose.local.yml --env-file .env restart nginx


.PHONY: build
build:
	make geoapi && make workers

.PHONY: geoapi
geoapi:
	docker build -t $(GEOAPI_IMAGE):$(TAG) -f devops/Dockerfile .
	docker tag $(GEOAPI_IMAGE):$(TAG) $(GEOAPI_IMAGE):latest
	docker tag $(GEOAPI_IMAGE):$(TAG) $(GEOAPI_IMAGE):local
	docker tag $(GEOAPI_IMAGE):$(TAG) $(GEOAPI_IMAGE):$(DOCKER_IMAGE_BRANCH_TAG)

.PHONY: workers
workers:
	docker build -t $(GEOAPI_WORKERS):$(TAG) -f devops/Dockerfile.worker .
	docker tag $(GEOAPI_WORKERS):$(TAG) $(GEOAPI_WORKERS):latest
	docker tag $(GEOAPI_WORKERS):$(TAG) $(GEOAPI_WORKERS):local
	docker tag $(GEOAPI_WORKERS):$(TAG) $(GEOAPI_WORKERS):$(DOCKER_IMAGE_BRANCH_TAG)


.PHONY: deploy
deploy:
	make deploy-geoapi && make deploy-workers

.PHONY: deploy-geoapi
deploy-geoapi:
	docker push $(GEOAPI_IMAGE):$(TAG)
	docker push $(GEOAPI_IMAGE):$(DOCKER_IMAGE_BRANCH_TAG)

.PHONY: deploy-workers
deploy-workers:
	docker push $(GEOAPI_WORKERS):$(TAG)
	docker push $(GEOAPI_WORKERS):$(DOCKER_IMAGE_BRANCH_TAG)

.PHONY: build-dev
build-dev:
	docker build -t $(GEOAPI_IMAGE):$(TAG) --target development -f devops/Dockerfile .
	docker build -t $(GEOAPI_WORKERS):$(TAG) --target development -f devops/Dockerfile.worker .
	docker tag $(GEOAPI_WORKERS):$(TAG) $(GEOAPI_WORKERS):local
	docker tag $(GEOAPI_IMAGE):$(TAG) $(GEOAPI_IMAGE):local
