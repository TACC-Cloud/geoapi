#!/bin/bash
set -ex

kubectl --context=wma-geospatial apply -f ~geoapi/util/production_assets_util.yaml
kubectl --context=geoapi-dev apply -f ~geoapi/util/staging_assets_util.yaml

echo "Removing backups older than 6 weeks (i.e. 42 days) (STAGING)"
ssh tg458981@ranch.tacc.utexas.edu 'find /stornext/ranch_01/ranch/projects/DesignSafe-Community/geoapi_assets_backup/staging/ -mtime +42 -type f -exec rm {} +'

echo "Backing up staging (skipping /assets/streetview as those are temp files)"
kubectl exec -i pod/staging-assets-util --context=geoapi-dev -- tar --exclude /assets/ --exclude /assets/streetview -c -f - /assets/ | ssh  tg458981@ranch.tacc.utexas.edu 'split -b 300G - /stornext/ranch_01/ranch/projects/DesignSafe-Community/geoapi_assets_backup/staging/staging_assets`date +%Y-%m-%d`.tar.'

echo "Finished with STAGING and beginning PRODUCTION"

echo "Removing backups older than 6 weeks (i.e. 42 days) (PRODUCTION)"
ssh tg458981@ranch.tacc.utexas.edu 'find /stornext/ranch_01/ranch/projects/DesignSafe-Community/geoapi_assets_backup/production/ -mtime +42 -type f -exec rm {} +'

echo "Backing up production (skipping /assets/streetview as those are temp files)"
kubectl exec -i pod/production-assets-util --context=wma-geospatial -- tar --exclude /assets/streetview -c -f - /assets/ | ssh  tg458981@ranch.tacc.utexas.edu 'split -b 300G - /stornext/ranch_01/ranch/projects/DesignSafe-Community/geoapi_assets_backup/production/production_assets`date +%Y-%m-%d`.tar.'
