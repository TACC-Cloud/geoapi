#!/bin/bash
set -xeuo pipefail

echo "Removing backups older than 1 week (i.e. 7 days) (STAGING)"
ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu \
  'find /scoutfs/projects/DesignSafe-Community/geoapi_assets_backup/staging/ -mtime +7 -type f -exec rm {} +'

echo "Backing up staging"
ssh -o StrictHostKeyChecking=no portal@staging.geoapi-services.tacc.utexas.edu bash -euo pipefail -c \
'tar -C / --exclude=assets/streetview --exclude=assets/lost+found --exclude=assets/bug -c -f - assets | ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu split -b 300G - /scoutfs/projects/DesignSafe-Community/geoapi_assets_backup/staging/staging_assets$(date +%F).tar.'

# size check for STAGING (>= 1 TiB)
ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu '
  D1=$(date +%F); D0=$(date -d "yesterday" +%F); P=/scoutfs/projects/DesignSafe-Community/geoapi_assets_backup/staging;
  SZ=$(du --apparent-size --bytes --total "$P"/staging_assets{$D0,$D1}.tar.* 2>/dev/null | awk "/total/{print \$1}");
  echo "Staging bytes: $SZ"; [ "${SZ:-0}" -ge "$(numfmt --from=si 1T)" ] || { echo "ERROR: < 1 TB"; exit 1; }
'

echo "Finished with STAGING and beginning PRODUCTION"
echo "--------------------------------------------------"
echo "--------------------------------------------------"

echo "Removing backups older than 3 weeks (i.e. 21 days) (PRODUCTION)"
ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu \
  'find /scoutfs/projects/DesignSafe-Community/geoapi_assets_backup/production/ -mtime +21 -type f -exec rm {} +'

echo "Backing up production"
ssh -o StrictHostKeyChecking=no portal@prod.geoapi-services.tacc.utexas.edu bash -euo pipefail -c \
'tar -C / --exclude=assets/streetview --exclude=assets/lost+found --exclude=assets/bug -c -f - assets | ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu split -b 300G - /scoutfs/projects/DesignSafe-Community/geoapi_assets_backup/production/production_assets$(date +%F).tar.'

# size check for PRODUCTION over today + yesterday (>= 3 TB)
ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu '
  D1=$(date +%F); D0=$(date -d "yesterday" +%F); P=/scoutfs/projects/DesignSafe-Community/geoapi_assets_backup/production;
  SZ=$(du --apparent-size --bytes --total "$P"/production_assets{$D0,$D1}.tar.* 2>/dev/null | awk "/total/{print \$1}");
  echo "Production bytes: $SZ"; [ "${SZ:-0}" -ge "$(numfmt --from=si 3T)" ] || { echo "ERROR: < 3 TB"; exit 1; }
'
