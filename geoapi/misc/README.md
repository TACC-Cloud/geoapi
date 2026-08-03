# `misc/` — one-off operational scripts

Ad-hoc scripts run by hand (not part of the API or the Celery schedule).

## `dry_run_published_ds_maps.py`

A dry run creating the published-DesignSafe-maps archive. Non-destructive: it
measures counts/sizes and writes to a scratch path, never the real
`assets/public` area or the manifest.

It writes two files:

- `/assets/tmp/published_ds_maps.pmtiles` — the tiled archive
- `/assets/tmp/published_ds_maps.vectors_and_internal_cogs.geojson` — the
  companion layer footprints (internal COGs + PMTiles-vector uploads)

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
