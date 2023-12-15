#!/bin/bash
set -ex

echo "Removing backups older than 6 weeks (i.e. 42 days) (STAGING)"
ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu 'find /stornext/ranch_01/ranch/projects/DesignSafe-Community/geoapi_assets_backup/staging/ -mtime +42 -type f -exec rm {} +'

echo "Backing up staging"
ssh -o StrictHostKeyChecking=no portal@prod.geoapi-services.tacc.utexas.edu "
set -ex
# skipping /assets/streetview as those are temp files
tar --exclude=/assets/streetview -c -f - /assets/ | \
ssh tg458981@ranch.tacc.utexas.edu 'split -b 300G - /stornext/ranch_01/ranch/projects/DesignSafe-Community/geoapi_assets_backup/staging/staging_assets\$(date +%Y-%m-%d).tar.'
"
echo "Finished with STAGING and beginning PRODUCTION"

echo "Removing backups older than 6 weeks (i.e. 42 days) (PRODUCTION)"
ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu 'find /stornext/ranch_01/ranch/projects/DesignSafe-Community/geoapi_assets_backup/production/ -mtime +42 -type f -exec rm {} +'

# testing
exit 1

echo "Backing up production"
ssh -o StrictHostKeyChecking=no portal@prod.geoapi-services.tacc.utexas.edu "
set -ex
# skipping /assets/streetview as those are temp files
tar --exclude=/assets/streetview -c -f - /assets/ | \
ssh tg458981@ranch.tacc.utexas.edu 'split -b 300G - /stornext/ranch_01/ranch/projects/DesignSafe-Community/geoapi_assets_backup/production/production_assets\$(date +%Y-%m-%d).tar.'
"