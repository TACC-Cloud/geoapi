#!/bin/bash
set -ex

echo "Removing backups older than 2 weeks (i.e. 14 days) (STAGING)"
ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu 'find /stornext/ranch_01/ranch/projects/DesignSafe-Community/geoapi_assets_backup/staging/ -mtime +14 -type f -exec rm {} +'

echo "Backing up staging"
ssh -o StrictHostKeyChecking=no portal@staging.geoapi-services.tacc.utexas.edu "
set -ex
# skipping /assets/streetview as those are temp files
tar --exclude=/assets/streetview --exclude=/assets/lost+found --exclude=/assets/bug/ -c -f - /assets/ | \
ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu 'split -b 300G - /stornext/ranch_01/ranch/projects/DesignSafe-Community/geoapi_assets_backup/staging/staging_assets\\$(date +%Y-%m-%d).tar.'
"

echo "Finished with STAGING and beginning PRODUCTION"

echo "--------------------------------------------------"
echo "--------------------------------------------------"

echo "Removing backups older than 4 weeks (i.e. 28 days) (PRODUCTION)"
ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu 'find /stornext/ranch_01/ranch/projects/DesignSafe-Community/geoapi_assets_backup/production/ -mtime +28 -type f -exec rm {} +'

echo "Backing up production"
ssh -o StrictHostKeyChecking=no portal@prod.geoapi-services.tacc.utexas.edu "
set -ex
# skipping /assets/streetview as those are temp files
tar --exclude=/assets/streetview  --exclude=/assets/lost+found --exclude=/assets/bug/ -c -f - /assets/ | \
ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu 'split -b 300G - /stornext/ranch_01/ranch/projects/DesignSafe-Community/geoapi_assets_backup/production/production_assets\\$(date +%Y-%m-%d).tar.'
"