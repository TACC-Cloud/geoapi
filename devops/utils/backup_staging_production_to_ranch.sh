#!/bin/bash
set -xeuo pipefail
echo "========================================"
echo "STEP 1: Cleanup old STAGING backups"
echo "========================================"
echo "Removing backups older than 1 week (i.e. 7 days) (STAGING)"
ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu \
  'find /scoutfs/projects/DesignSafe-Community/geoapi_assets_backup/staging/ -mtime +7 -type f -exec rm {} +'
echo "✓ Cleanup complete"
echo ""
echo "========================================"
echo "STEP 2: Backup STAGING assets"
echo "========================================"
ssh -o StrictHostKeyChecking=no portal@staging.geoapi-services.tacc.utexas.edu "bash --norc -c 'set -eo pipefail; tar -C / --exclude=assets/tmp --exclude=assets/streetview --exclude=assets/lost+found --exclude=assets/bug --warning=no-file-changed -c -f - assets | ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu split -b 300G - /scoutfs/projects/DesignSafe-Community/geoapi_assets_backup/staging/staging_assets\$(date +%F).tar.'"
echo "✓ STAGING backup complete"
echo ""
echo "========================================"
echo "STEP 3: Verify STAGING backup size"
echo "========================================"
ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu '
  D1=$(date +%F); D0=$(date -d "yesterday" +%F); P=/scoutfs/projects/DesignSafe-Community/geoapi_assets_backup/staging;
  SZ=$(du --apparent-size --bytes --total "$P"/staging_assets{$D0,$D1}.tar.* 2>/dev/null | awk "/total/{print \$1}");
  echo "Staging bytes: $SZ"; [ "${SZ:-0}" -ge "$(numfmt --from=si 1T)" ] || { echo "ERROR: < 1 TB"; exit 1; }
'
echo "✓ Size verification passed"
echo ""
echo "========================================"
echo "STEP 4: Cleanup old PRODUCTION backups"
echo "========================================"
echo "Removing backups older than 3 weeks (i.e. 21 days) (PRODUCTION)"
ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu \
  'find /scoutfs/projects/DesignSafe-Community/geoapi_assets_backup/production/ -mtime +21 -type f -exec rm {} +'
echo "✓ Cleanup complete"
echo ""
echo "========================================"
echo "STEP 5: Backup PRODUCTION assets"
echo "========================================"
ssh -o StrictHostKeyChecking=no portal@prod.geoapi-services.tacc.utexas.edu "bash --norc -c 'set -eo pipefail; tar -C / --exclude=assets/tmp --exclude=assets/streetview --exclude=assets/lost+found --exclude=assets/bug --warning=no-file-changed -c -f - assets | ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu split -b 300G - /scoutfs/projects/DesignSafe-Community/geoapi_assets_backup/production/production_assets\$(date +%F).tar.'"
echo "✓ PRODUCTION backup complete"
echo ""
echo "========================================"
echo "STEP 6: Verify PRODUCTION backup size"
echo "========================================"
ssh -o StrictHostKeyChecking=no tg458981@ranch.tacc.utexas.edu '
  D1=$(date +%F); D0=$(date -d "yesterday" +%F); P=/scoutfs/projects/DesignSafe-Community/geoapi_assets_backup/production;
  SZ=$(du --apparent-size --bytes --total "$P"/production_assets{$D0,$D1}.tar.* 2>/dev/null | awk "/total/{print \$1}");
  echo "Production bytes: $SZ"; [ "${SZ:-0}" -ge "$(numfmt --from=si 3T)" ] || { echo "ERROR: < 3 TB"; exit 1; }
'
echo "✓ Size verification passed"
