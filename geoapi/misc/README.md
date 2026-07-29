# `misc/` — one-off operational scripts

Ad-hoc scripts run by hand (not part of the API or the Celery schedule). Today
there is just one.

## `dry_run_published_ds_maps.py`

A **non-destructive** dry run of the WG-703 published-DesignSafe-maps archive. It
runs the real selector → exporter → tiler against whatever database the
environment points at and prints:

- project / feature / COG-footprint counts and a per-`feature_type` breakdown,
- per-feature property-payload sizes (which keys are heaviest — informs whether to
  split project-level fields into a companion `projects.json`),
- the archive bounds, and
- the **total archive size**.

It writes the archive to `/assets/tmp/published_ds_maps.pmtiles` (a scratch path,
never `/assets/public/`); delete it when done.

### Run against the local dev stack

```bash
docker exec -it geoapi_workers python misc/dry_run_published_ds_maps.py
```

### Run against production

The deployed geoapi containers get their DB password, `APP_ENV`, etc. from a
secrets file on the host — see `Core-Portal-Deployments/geoapi-services/camino/docker-compose.yml`,
where `backend` and `celerybeat` use `env_file: /opt/portal/conf/secrets.env`.
Reuse that same file for a one-off container (org/tag come from `prod.env`):

```bash
docker run --rm \
  --env-file /opt/portal/conf/secrets.env \
  -v /assets:/assets \
  taccwma/geoapi-workers:<GEOAPI_TAG> \
  python misc/dry_run_published_ds_maps.py
```
