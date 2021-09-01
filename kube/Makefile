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


.PHONY: deploy
deploy: checkforcontext checkfortag
deploy: ## Create deployment/services/jobs of geoapi (PRODUCTION) !!!  CAREFUL !
	kubectl delete --context $(KUBE_CONTEXT) --ignore-not-found=true  deployment geoapi geoapi-workers geoapi-celerybeat
	kubectl delete --context $(KUBE_CONTEXT) --ignore-not-found=true  job/geoapi-migrations
	source ${ENV_FILE} && cat geoapi.deployment.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP}' | kubectl apply --context $(KUBE_CONTEXT) -f -
	source ${ENV_FILE} && cat workers.deployment.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP}' | kubectl apply --context $(KUBE_CONTEXT) -f -
	source ${ENV_FILE} && cat celerybeat.deployment.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP}' | kubectl apply --context $(KUBE_CONTEXT) -f -
	source ${ENV_FILE} && cat migrations.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP}' | kubectl apply --context $(KUBE_CONTEXT) -f -

.PHONY: deploy-prod
deploy-prod: KUBE_CONTEXT=wma-geospatial
deploy-prod: ENV_FILE=prod.env
deploy-prod: deploy
	@echo "Finished creating geoapi (deployment/services/jobs) in '$(KUBE_CONTEXT)' context using ${ENV_FILE} file"


.PHONY: deploy-staging
deploy-prod: KUBE_CONTEXT=geoapi
deploy-prod: ENV_FILE=staging.env
deploy-prod: deploy
	@echo "Finished creating geoapi (deployment/services/jobs) in '$(KUBE_CONTEXT)' context using ${ENV_FILE} file"

.PHONY: burnup-prod
burnup-prod: KUBE_CONTEXT=wma-geospatial
burnup-prod: ENV_FILE=prod.env
	source ${ENV_FILE} && cat configMaps.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP}' | kubectl apply --context $(KUBE_CONTEXT) -f -
	source ${ENV_FILE} && cat nfsshare.pvc.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP}' | kubectl apply --context $(KUBE_CONTEXT) -f -
	source ${ENV_FILE} && cat nfsshare.service.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP}' | kubectl apply --context $(KUBE_CONTEXT) -f -
	source ${ENV_FILE} && cat nfsshare.deployment.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP}' | kubectl apply --context $(KUBE_CONTEXT) -f -
	source ${ENV_FILE} && cat nginx.service.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP}' | kubectl apply --context $(KUBE_CONTEXT) -f -
	source ${ENV_FILE} && cat nginx.deployment.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP}' | kubectl apply --context $(KUBE_CONTEXT) -f -
	source ${ENV_FILE} && cat postgres.pvc.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP}' | kubectl apply --context $(KUBE_CONTEXT) -f -
	source ${ENV_FILE} && cat postgres.service.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP}' | kubectl apply --context $(KUBE_CONTEXT) -f -
	source ${ENV_FILE} && cat postgres.deployment.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP}' | kubectl apply --context $(KUBE_CONTEXT) -f -
	source ${ENV_FILE} && cat rabbitmq.service.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP}' | kubectl apply --context $(KUBE_CONTEXT) -f -
	source ${ENV_FILE} && cat rabbitmq.deployment.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP}' | kubectl apply --context $(KUBE_CONTEXT) -f -
	source ${ENV_FILE} && cat geoapi.service.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP}' | kubectl apply --context $(KUBE_CONTEXT) -f -
	source ${ENV_FILE} && cat geoapi.deployment.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP}' | kubectl apply --context $(KUBE_CONTEXT) -f -
	source ${ENV_FILE} && cat workers.deployment.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP}' | kubectl apply --context $(KUBE_CONTEXT) -f -
	source ${ENV_FILE} && cat celerybeat.deployment.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP}' | kubectl apply --context $(KUBE_CONTEXT) -f -
	source ${ENV_FILE} && cat migrations.yaml | envsubst '$${GEOAPI_TAG} $${NODEPORT} $${NSFSHARE_CLUSTER_IP}' | kubectl apply --context $(KUBE_CONTEXT) -f -




