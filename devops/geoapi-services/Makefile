
.PHONY: start
start:
	docker compose -f docker-compose.yml up -d

.PHONY: stop
stop:
	docker compose -f docker-compose.yml down

.PHONY: pull
pull:
    docker pull api workers nginx rabbitmq