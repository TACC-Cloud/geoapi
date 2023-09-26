
.PHONY: start
start:
	echo "starting (GEOAPI_TAG=${GEOAPI_TAG})"
	#docker compose -f docker-compose.yml up -d
	docker compose -f docker-compose.yml up 

.PHONY: stop
stop:
	docker compose -f docker-compose.yml down

.PHONY: pull
pull:
	docker compose pull api workers nginx rabbitmq
