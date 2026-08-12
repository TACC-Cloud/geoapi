# GeoAPI MCP Server — Local Testing

Assumes the geoapi server is already running locally on port 8001.

## 1. Generate `.mcp.json`

```bash
python setup_mcp.py
```

Prompts for your Tapis username/password, fetches a JWT from `designsafe.tapis.io`, and writes `.mcp.json` with the `geoapi` server registered.

## 2. Run Claude

Run from this directory (`mcp/local_testing/`) so Claude picks up the generated `.mcp.json` and the `.claude/` settings:

```bash
cd mcp/local_testing
claude
```

Then prompt naturally, e.g.:

> list the files in my My Data and tell me which look geospatial

> inspect image1.jpg in my My Data

> inspect /nathanf/image.jpg on system designsafe.storage.default

> inspect /published-data/PRJ-3379/Mission--marshall-fire-reconnaissance-2022/data/Geoscience-collection--raw-data/data/RApp/uwrapid/Home/0124mul04.jpg on system designsafe.storage.published

> list my maps

> which of my maps do I own vs. just collaborate on?

The `list` prompt calls `list_files` — a cheap, extension-only survey of a folder (`yes`/`no`/`maybe` per file). The `inspect` prompts call `inspect_file` for a real GDAL/OGR/PDAL verdict. The `maps` prompts call `list_maps`, which returns your maps plus your role on each (`creator`/`admin`). A natural end-to-end flow is *list a folder → inspect the promising ones → import a geospatial one into a map you own* (the agent will warn before adding files to a map you don't own).

**Note:** the token is static in the header for personal local testing. JWTs expire (~4 hrs) — re-run `setup_mcp.py` when it goes stale.

## Example paths to try (published DesignSafe reconnaissance data)

All on system `designsafe.storage.published`. These are reconnaissance **JPEGs** — a good way to see the difference between the cheap `list` guess and the real `inspect` verdict.

How images work here: `inspect` reads **EXIF geolocation** for JPEGs. A geotagged photo comes back `is_geospatial: true`, `kind: "image"` with its lat/lon — i.e. importable to Hazmapper as a point feature; a photo with no GPS comes back `is_geospatial: false` (a plain image, which Hazmapper's import would reject). `list`, being extension-only, just guesses `maybe` for any `.jpg` — it can't see EXIF cheaply. So this set demos `list`'s cheap guess vs. `inspect`'s real, EXIF-aware verdict.

**Set 1 — Hurricane Michael (PRJ-2113, StEER)**

> Inspect these on `designsafe.storage.published` and tell me which are geospatial:
> - `/PRJ-2113/D6.2 Other Ground Based Imagery - RAPID EF/06_Waterfront Appartments_20181108/Canon Photos/1A7A1046.JPG`
> - `/PRJ-2113/D6.2 Other Ground Based Imagery - RAPID EF/06_Waterfront Appartments_20181108/Canon Photos/1A7A1047.JPG`
> - `/PRJ-2113/D6.2 Other Ground Based Imagery - RAPID EF/02_Water Tower_20181107/Canon Photos/Scene/1A7A0844.JPG`

**Set 2 — Western European Floods 2021 (PRJ-3252 / PRJ-3442, GEER & RAPID)**

> Inspect these on `designsafe.storage.published`:
> - `/PRJ-3442v2/RAPID_EF/3_Deliverables/Mayschoss/Imagery/0329-pedbridge-mayschoss_s1_compass_4xC16L-A_11.jpg`
> - `/PRJ-3252/Germany (August 9-13, 2021)/Sinzig (August 12)/Photos/MGeorge/PXL_20210812_101136279.jpg`
> - `/PRJ-3252/Germany (August 9-13, 2021)/Sinzig (August 12)/Photos/MGeorge/PXL_20210812_110558490.jpg`
> - `/PRJ-3252/Germany (August 9-13, 2021)/Green (August 12)/Photos/MGeorge/PXL_20210812_135723068.jpg`
> - `/PRJ-3252/Germany (August 9-13, 2021)/Bliesheim - Bridge Merowingerstr (August 10)/Photos/NStark/20210810_105642.jpg`

**Set 3 — Wildfires & Haiti earthquake (PRJ-5857, PRJ-3379, PRJ-3269)**

> Inspect these on `designsafe.storage.published`:
> - `/PRJ-5857/Mission 05/Pacific Palisades/Photos/Craig Davis/IMG_6649.JPG`
> - `/PRJ-5857/Mission 05/Pacific Palisades/Photos/Marty Hudson/2025-02-08-12-57-24.jpg`
> - `/PRJ-5857/Mission 05/Pacific Palisades/Photos/Marty Hudson/2025-02-08-12-56-57.jpg`
> - `/PRJ-3379/RApp/uwrapid/Home/Photo 1642618419.jpg`
> - `/PRJ-3269/D1. Performance Assessments/Images/0002898c-8807-44e6-94cd-afeb959d13fb.jpg`

**A whole folder (exercises recursion)**

> List everything under `/PRJ-2113/D6.2 Other Ground Based Imagery - RAPID EF/06_Waterfront Appartments_20181108/Canon Photos` on `designsafe.storage.published` and tell me which look geospatial.

> Do a shallow (non-recursive) listing of `/PRJ-3252` on `designsafe.storage.published` so I can see its sub-folders first.

## TODO

- Use Tejas / SambaNova instead of Claude.
