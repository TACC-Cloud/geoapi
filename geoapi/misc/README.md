# `misc/` — one-off operational scripts

Ad-hoc scripts run by hand (not part of the API or the Celery schedule).

## `dry_run_published_ds_maps.py`

A dry run creating the published-DesignSafe-maps archive.

It writes the archive to `/assets/tmp/published_ds_maps.pmtiles`

### Run against the local dev stack

```bash
docker exec -it geoapi_workers python misc/dry_run_published_ds_maps.py
```

### Run against production

```bash
docker run --rm \
  --env-file /opt/portal/conf/secrets.env \
  -v /assets:/assets \
  taccwma/geoapi-workers:<GEOAPI_TAG> \
  python misc/dry_run_published_ds_maps.py
```
