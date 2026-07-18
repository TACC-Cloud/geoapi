# geoapi-mcp

A [FastMCP](https://gofastmcp.com) server that exposes GeoAPI's file endpoints as
agent tools. It is a **client of GeoAPI over HTTP** — it does no geospatial work and
holds no state.

```
agent service ──MCP (HTTP)──► geoapi-mcp ──REST──► GeoAPI
                                                    ├─ POST /files/inspect
                                                    └─ existing import endpoints
```

## Tools

| Tool | Calls | Notes |
|------|-------|-------|
| `list_files(system_id, path)` | `POST /files/list` | Cheap, extension-only geospatial guess per file (`yes`/`no`/`maybe`). `path` may be a file or directory (recursive). Survey first, then inspect. |
| `inspect_file(system_id, path)` | `POST /files/inspect` | Deterministic geospatial verdict (GDAL/OGR/PDAL). `path` may be a file or a directory (recursive); returns a **list** of per-file verdicts. |
| `import_file(system_id, path, project_id, label=None)` | existing per-kind import endpoints | Routes raster → `/tile-servers/files/import/`, vector/images → `/features/files/import/`. **Point clouds not supported yet** (see the TODO in `server.py`). |
| `list_maps()` | `GET /projects/` | The user's own maps (token-scoped). Use a map's `id` as `project_id`. |
| `create_map(name, description="", location="DESIGN_SAFE_MY_DATA")` | `POST /projects/` | Create a new **private** map under My Data (default) or a DesignSafe project (pass its `project-XXXX` system id). Confirm name + location first (a WRITE). Publishing is done later in the Hazmapper web app. |

The tool docstrings steer the agent: survey/inspect first, and only import a file the
verdict marked `is_geospatial: true` after the user confirms — never import a
non-geospatial file. All authorization is enforced by GeoAPI (e.g. a 403 if the user may
not write to a map); the MCP itself enforces nothing.

**My Data shortcut:** for the user's DesignSafe My Data, pass `system_id="DESIGN_SAFE_MY_DATA"`
and a home-relative path to `list_files` / `inspect_file` / `import_file`. The MCP resolves it to
`designsafe.storage.default` at `/<username>` (username decoded from the token), so the
agent never has to know or ask for the username. (GeoAPI still rejects listing the raw
`designsafe.storage.default` root, since that's the shared root of all users.)

## Design rules (keep it self-contained)

- **Never imports the `geoapi` package.** HTTP only. This is what keeps the image tiny
  and separately deployable.
- **Separate dependencies:** `fastmcp` + `httpx`, nothing else. No GDAL/PDAL/Celery/PostGIS.
- **Separate image** (`Dockerfile`) with its own healthcheck.
- **Tests use their own fixtures** under `tests/fixtures/` — they do NOT read from
  `../geoapi/tests/fixtures/`.

## Auth — Tapis JWT pass-through

On each request it reads the  caller's Tapis JWT from `X-Tapis-Token` and forwards it
verbatim as `X-Tapis-Token` to GeoAPI, which does all validation via its existing JWT
middleware. The token is **per-request** (not an env var), which is what makes the server
multi-user-safe.

## Configuration

| Env var | Default | Meaning |
|---------|---------|---------|
| `GEOAPI_BASE_URL` | `http://geoapi:8000` | Base URL of the GeoAPI service. |
| `GEOAPI_HTTP_TIMEOUT` | `60` | Per-request timeout (seconds). |
| `MCP_HOST` | `0.0.0.0` | Bind host. |
| `MCP_PORT` | `8001` | Bind port. |

## Run

```bash
# Local (from this directory)
pip install .
GEOAPI_BASE_URL=http://localhost:8000 python server.py   # serves streamable HTTP on :8001

# Or with the whole stack
docker compose up   # see repo-root docker-compose additions
```

## Test

```bash
pip install .[dev]
pytest
# or, no local install:
uv run --with fastmcp --with httpx --with pytest --with respx pytest
```
