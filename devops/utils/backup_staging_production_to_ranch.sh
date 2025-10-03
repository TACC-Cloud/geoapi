#!/bin/bash
set -Exeuo pipefail

echo "Removing backups older than 1 week (i.e. 7 days) (STAGING)"
ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu \
  'find /scoutfs/projects/DesignSafe-Community/geoapi_assets_backup/staging/ -mtime +7 -type f -exec rm {} +'

echo "Backing up staging"
ssh -o StrictHostKeyChecking=no portal@staging.geoapi-services.tacc.utexas.edu bash -lc '
  set -Exeuo pipefail

  # skipping /assets/streetview as those are temp files
  tar \
      -C / \
      --exclude=assets/streetview \
      --exclude=assets/lost+found \
      --exclude=assets/bug \
      -c -f - assets \
  | ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu \
      split -b 300G - /scoutfs/projects/DesignSafe-Community/geoapi_assets_backup/staging/staging_assets$(date +%Y-%m-%d).tar.
'

echo "Finished with STAGING and beginning PRODUCTION"
echo "--------------------------------------------------"
echo "--------------------------------------------------"

echo "Removing backups older than 3 weeks (i.e. 21 days) (PRODUCTION)"
ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu \
  'find /scoutfs/projects/DesignSafe-Community/geoapi_assets_backup/production/ -mtime +21 -type f -exec rm {} +'

echo "Backing up production"
ssh -o StrictHostKeyChecking=no portal@prod.geoapi-services.tacc.utexas.edu bash -lc '
  set -Exeuo pipefail
  # skipping /assets/streetview as those are temp files
  tar \
      -C / \
      --exclude=assets/streetview \
      --exclude=assets/lost+found \
      --exclude=assets/bug \
      -c -f - assets \
  | ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu \
      split -b 300G - /scoutfs/projects/DesignSafe-Community/geoapi_assets_backup/production/production_assets$(date +%Y-%m-%d).tar.
'
