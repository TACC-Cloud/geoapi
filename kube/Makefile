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

.PHONY: checkfortag
checkfortag:
	@if test -z "$(GEOAPI_TAG)"; then\
		 echo "Missing GEOAPI_TAG needed for images";\
		 exit 1;\
	fi
	@echo "Using '$(GEOAPI_TAG)' images"

.PHONY: create
create: checkforcontext checkfortag
	@echo "Creating geoapi deployment/services/migration-job in '$(KUBE_CONTEXT)' context"
	source ${ENV_FILE} && cat geoapi.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP} $${PGDATA_PVC} $${PGDATA_PVC_SIZE=750G}' | kubectl apply --context $(KUBE_CONTEXT) -f -

.PHONY: delete
delete: checkforcontext
	@echo "Deleting geoapi deployment/services/migration-job in '$(KUBE_CONTEXT)' context"
	kubectl delete --context $(KUBE_CONTEXT) --ignore-not-found=true  deployment geoapi geoapi-workers geoapi-celerybeat geoapi-nginx geoapi-postgres geoapi-rabbitmq
	kubectl delete --context $(KUBE_CONTEXT) --ignore-not-found=true service geoapi geoapi-nginx geoapi-postgres geoapi-rabbitmq
	kubectl delete --context $(KUBE_CONTEXT) --ignore-not-found=true job/geoapi-migrations

.PHONY: delete-staging
delete-staging: KUBE_CONTEXT=geoapi-dev
delete-staging: delete ## Delete deployment/services/jobs of geoapi (STAGING)
	@echo "Finished deleting geoapi (deployment/services/jobs) in '$(KUBE_CONTEXT)' context"

.PHONY: create-staging
create-staging: KUBE_CONTEXT=geoapi-dev
create-staging: ENV_FILE=staging.env
create-staging: create ## Create deployment/services/jobs of geoapi (STAGING)
	@echo "Finished creating geoapi (deployment/services/jobs) in '$(KUBE_CONTEXT)' context using ${ENV_FILE} file"

.PHONY: delete-production
delete-production: KUBE_CONTEXT=wma-geospatial
delete-production: delete ## Delete deployment/services/jobs of geoapi (PRODUCTION) !!!  CAREFUL !
	@echo "Finished deleting geoapi (deployment/services/jobs) in '$(KUBE_CONTEXT)' context"

.PHONY: delete-staging
create-production: KUBE_CONTEXT=wma-geospatial
create-production: ENV_FILE=prod.env
create-production: create ## Create deployment/services/jobs of geoapi (PRODUCTION) !!!  CAREFUL !
	@echo "Finished creating geoapi (deployment/services/jobs) in '$(KUBE_CONTEXT)' context using ${ENV_FILE} file"
