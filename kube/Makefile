help:   ## Show this help.
	@echo ""
	@echo "Possible Commands:"
	@echo ""
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/\\$$//' | sed -e 's/##//'
	@echo ""
	@echo ""
	@echo "Examples:"
	@echo ""
	@echo "To delete services/deployments on staging context"
	@echo "   make KUBE_CONTEXT="geoapi-dev" delete" 

.PHONY: checkforcontext
checkforcontext:
	@if test -z "$(KUBE_CONTEXT)"; then\
		 echo "Missing context";\
		 exit 1;\
	fi
	@echo "context is $(KUBE_CONTEXT)"

.PHONY: delete
delete: checkforcontext  ## Delete deployment/services/jobs of geoapi
	echo $(KUBE_CONTEXT)
	kubectl delete --context $(KUBE_CONTEXT)  deployment geoapi geoapi-workers geoapi-celerybeat geoapi-nginx geoapi-postgres geoapi-rabbitmq
	kubectl delete --context $(KUBE_CONTEXT) service geoapi geoapi-nginx geoapi-postgres geoapi-rabbitmq
	kubectl delete --context $(KUBE_CONTEXT) job/geoapi-migrations
