.PHONY: start
start:
    echo "starting services GEOAPI_TAG=$GEOAPI_TAG"
	docker-compose -f docker-compose.yml up

.PHONY: stop
stop:
    echo "stopping services (GEOAPI_TAG=$GEOAPI_TAG)"
	docker-compose -f docker-compose.yml down
