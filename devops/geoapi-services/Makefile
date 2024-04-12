
.PHONY: start
start:
	echo "starting (NGINX_SERVER_NAME=${NGINX_SERVER_NAME}  GEOAPI_TAG=${GEOAPI_TAG} HAZMAPPER_TAG=${HAZMAPPER_TAG} TAGGIT_TAG=${TAGGIT_TAG})"
	docker compose -f docker-compose.yml up -d

.PHONY: stop
stop:
	docker compose -f docker-compose.yml down

.PHONY: pull
pull:
	docker compose pull api workers nginx rabbitmq hazmapper taggit
