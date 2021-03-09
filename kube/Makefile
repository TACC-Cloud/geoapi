SHELL := /bin/bash


help:   ## Show this help.
	@echo ""
	@echo "Possible Commands:"
	@echo ""
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/\\$$//' | sed -e 's/##//'
	@echo ""

.PHONY: checkforcontext
checkforcontext:
	@if test -z "$(KUBE_CONTEXT)"; then\
		 echo "Missing context";\
		 exit 1;\
	fi
	@echo "Using '$(KUBE_CONTEXT)' context"

.PHONY: create
create: checkforcontext
	@echo "Creating geoapi deployment/services/migration-job in '$(KUBE_CONTEXT)' context"
	source ${ENV_FILE} && cat geoapi.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP}' | kubectl apply -f - 

.PHONY: delete
delete: checkforcontext
	@echo "Deleting geoapi deployment/services/migration-job in '$(KUBE_CONTEXT)' context"
	kubectl delete --context $(KUBE_CONTEXT)  deployment geoapi geoapi-workers geoapi-celerybeat geoapi-nginx geoapi-postgres geoapi-rabbitmq
	kubectl delete --context $(KUBE_CONTEXT) service geoapi geoapi-nginx geoapi-postgres geoapi-rabbitmq
	kubectl delete --context $(KUBE_CONTEXT) job/geoapi-migrations

.PHONY: delete-staging
delete-staging: KUBE_CONTEXT=geoapi-dev
delete-staging: delete ## Delete deployment/services/jobs of geoapi
	@echo "Finished deleting geoapi in '$(KUBE_CONTEXT)' context"

.PHONY: delete-staging
create-staging: KUBE_CONTEXT=geoapi-dev
create-staging: ENV_FILE=staging.env
create-staging: create ## Create deployment/services/jobs of geoapi
	@echo "Finished creating geoapi in '$(KUBE_CONTEXT)' context using ${ENV_FILE} file"
