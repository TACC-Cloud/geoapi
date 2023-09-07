#!/bin/bash
set -ex

#starting production-assets-util
kubectl --context=wma-geospatial apply -f ~geoapi/util/production_assets_util.yaml
#starting staging-assets-util
kubectl --context=geoapi-dev apply -f ~geoapi/util/staging_assets_util.yaml

# Function to check if both pods are in the "Running" state
function are_pods_running() {
    local pod1_status=$(kubectl --context=wma-geospatial get pods production-assets-util  -o jsonpath='{.status.phase}')
    local pod2_status=$(kubectl --context=geoapi-dev get pods staging-assets-util -o jsonpath='{.status.phase}')

    if [[ "$pod1_status" == "Running" ]] && [[ "$pod2_status" == "Running" ]]; then
        return 0  # Both pods are running
    else
        return 1  # At least one pod is not running
    fi
}

# Wait for both pods to be ready
while ! are_pods_running; do
    echo "Waiting 30s for utility pods to be ready..."
    sleep 30
done

echo "Both utility pods are ready."

echo "Removing backups older than 6 weeks (i.e. 42 days) (STAGING)"
ssh tg458981@ranch.tacc.utexas.edu 'find /stornext/ranch_01/ranch/projects/DesignSafe-Community/geoapi_assets_backup/staging/ -mtime +42 -type f -exec rm {} +'

echo "Backing up staging (skipping /assets/streetview as those are temp files)"
kubectl exec -i pod/staging-assets-util --context=geoapi-dev -- tar --exclude /assets/ --exclude /assets/streetview -c -f - /assets/ | ssh  tg458981@ranch.tacc.utexas.edu 'split -b 300G - /stornext/ranch_01/ranch/projects/DesignSafe-Community/geoapi_assets_backup/staging/staging_assets`date +%Y-%m-%d`.tar.'

echo "Finished with STAGING and beginning PRODUCTION"

echo "Removing backups older than 6 weeks (i.e. 42 days) (PRODUCTION)"
ssh tg458981@ranch.tacc.utexas.edu 'find /stornext/ranch_01/ranch/projects/DesignSafe-Community/geoapi_assets_backup/production/ -mtime +42 -type f -exec rm {} +'

echo "Backing up production (skipping /assets/streetview as those are temp files)"
kubectl exec -i pod/production-assets-util --context=wma-geospatial -- tar --exclude /assets/streetview -c -f - /assets/ | ssh  tg458981@ranch.tacc.utexas.edu 'split -b 300G - /stornext/ranch_01/ranch/projects/DesignSafe-Community/geoapi_assets_backup/production/production_assets`date +%Y-%m-%d`.tar.'