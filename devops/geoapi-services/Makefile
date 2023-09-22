ENV_FILE ?= /opt/portal/secrets.env
# get GEOAPI_TAG and HAZMAPPER_TAG to be used by docker-compose.yml
include $(ENV_FILE)

.PHONY: start
start:
	docker-compose -f docker-compose.yml up

.PHONY: stop
stop:
	docker-compose -f docker-compose.yml down
