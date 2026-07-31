import shapely.geometry
from typing import List, Optional, Tuple
from urllib.parse import quote

from geoapi.log import logging
from geoapi.models import Feature, TileServer
from geoapi.custom.designsafe.published_maps import PublishedMap
from geoapi.utils.client_backend import (
    get_deployed_geoapi_url,
    get_deployed_hazmapper_url,
)

logger = logging.getLogger(__name__)

# DesignSafe published-data browser URL for a PRJ-#### project.
DESIGNSAFE_PUBLISHED_BROWSER_URL = (
    "https://www.designsafe-ci.org/data/browser/public/"
    "designsafe.storage.published/{designsafe_project_id}"
)

# A footprint wider/taller than this many degrees is logged as a likely georef error.
LARGE_EXTENT_WARN_DEG = 30

# TODO(from WG-703): brittle, project-specific guard. PRJ-6361 holds nation-wide image
# footprints (a large filled rectangle per image) that render poorly on the
# consumer (e.g. Recon Portal), so we leave them out for now. When the next such
# case appears, replace this with a general policy or figure out how to display
# these large datasets better on the consumer. Skip any PRJ-6361 geometry wider
# or taller than this many degrees.
PRJ_6361_PROJECT_ID = "PRJ-6361"
PRJ_6361_MAX_EXTENT_DEG = 4

# asset_type (FeatureAsset) -> feature_type for tiled features. "vector" is handled
# separately as a layer footprint; other unlisted types fall through to a
# geometry-based point/shape classification.
_ASSET_TYPE_TO_FEATURE_TYPE = {
    "image": "image",
    "video": "video",
    "point_cloud": "point_cloud",
    "streetview": "streetview",
    "questionnaire": "questionnaire",
}


class PublishedMapsExportService:
    """Turn selected published maps into GeoJSON for the public archive.

    Emits per-Hazmapper-feature dicts for the tiled PMTiles archive, plus layer
    footprints (internal COGs and PMTiles-vector uploads) for a companion GeoJSON
    rendered client-side. Every feature carries a property set that Recon Portal
    uses.
    """

    @classmethod
    def build_features(
        cls, database_session, published_maps: List[PublishedMap]
    ) -> Tuple[List[dict], List[dict], dict]:
        """Build the tiled features and the layer footprints.

        :return: ``(features, layer_features, stats)``. ``features`` are the
            per-Hazmapper-feature dicts tiled into the PMTiles archive.
            ``layer_features`` are footprints for internal COGs and PMTiles-vector
            uploads, written to the companion GeoJSON and rendered client-side.
            ``stats`` has ``feature_count`` (tiled), ``cog_count``,
            ``vector_count``, ``skipped_count`` (oversized geometries dropped),
            ``project_count`` and ``total`` (tiled).
        """
        geoapi_base = get_deployed_geoapi_url()
        hazmapper_base = get_deployed_hazmapper_url()

        features: List[dict] = []
        layer_features: List[dict] = []
        feature_count = 0
        cog_count = 0
        vector_count = 0
        skipped_count = 0

        for published in published_maps:
            project = published.project
            common = {
                "hazmapper_project_uuid": str(project.uuid),
                "hazmapper_project_name": project.name,
                "ds_project_name": published.designsafe_project_title,
                "ds_project_url": DESIGNSAFE_PUBLISHED_BROWSER_URL.format(
                    designsafe_project_id=published.designsafe_project_id
                ),
                "hazmapper_url": cls._hazmapper_url(hazmapper_base, project.uuid),
            }

            for feature in (
                database_session.query(Feature)
                .filter(Feature.project_id == project.id)
                .all()
            ):
                try:
                    geometry = feature.geometry
                except Exception:
                    logger.warning(
                        "Feature %s has unreadable geometry; skipping.", feature.id
                    )
                    continue
                if not geometry:
                    continue

                # a PMTiles-vector upload -> layer footprint (pointer to its own
                # tiles), not tiled here
                vector_asset = next(
                    (a for a in feature.assets if a.asset_type == "vector"), None
                )
                if vector_asset:
                    layer_features.append(
                        cls._vector_footprint(
                            feature, geometry, vector_asset, common, geoapi_base
                        )
                    )
                    vector_count += 1
                    continue

                if published.designsafe_project_id == PRJ_6361_PROJECT_ID:
                    minx, miny, maxx, maxy = shapely.geometry.shape(geometry).bounds
                    width_deg, height_deg = abs(maxx - minx), abs(maxy - miny)
                    if max(width_deg, height_deg) > PRJ_6361_MAX_EXTENT_DEG:
                        logger.info(
                            "Skipping feature %s: geometry spans %.1f x %.1f deg; "
                            "a feature this large renders poorly on the consumer "
                            "(e.g. Recon Portal), so leaving out for now.",
                            feature.id,
                            width_deg,
                            height_deg,
                        )
                        skipped_count += 1
                        continue

                properties = dict(common)
                properties.update(
                    {
                        "feature_id": feature.id,
                        "feature_type": cls._feature_type(feature),
                    }
                )
                features.append(
                    {"type": "Feature", "geometry": geometry, "properties": properties}
                )
                feature_count += 1

            for tile_server in (
                database_session.query(TileServer)
                .filter(TileServer.project_id == project.id)
                .filter(TileServer.internal.is_(True))
                .filter(TileServer.kind == "cog")
                .all()
            ):
                footprint = cls._cog_footprint(tile_server, common, geoapi_base)
                if footprint:
                    layer_features.append(footprint)
                    cog_count += 1

        stats = {
            "feature_count": feature_count,
            "cog_count": cog_count,
            "vector_count": vector_count,
            "skipped_count": skipped_count,
            "project_count": len(published_maps),
            "total": len(features),
        }
        logger.info(
            "Public export built %s tiled feature(s) + %s COG + %s vector "
            "footprint(s) across %s project(s); skipped %s oversized geometry(ies).",
            feature_count,
            cog_count,
            vector_count,
            stats["project_count"],
            skipped_count,
        )
        return features, layer_features, stats

    @staticmethod
    def _feature_type(feature) -> str:
        for asset in feature.assets:
            mapped = _ASSET_TYPE_TO_FEATURE_TYPE.get(asset.asset_type)
            if mapped:
                return mapped
        geometry_type = ((feature.geometry or {}).get("type") or "").lower()
        return "point" if "point" in geometry_type else "shape"

    @staticmethod
    def _hazmapper_url(hazmapper_base, project_uuid) -> str:
        return f"{hazmapper_base}/project-public/{project_uuid}"

    @classmethod
    def _cog_footprint(cls, tile_server, common, geoapi_base) -> Optional[dict]:
        tile_options = tile_server.tileOptions or {}
        bounds = tile_options.get("bounds")
        # bounds is leaflet-style [[minLat, minLng], [maxLat, maxLng]]
        if not bounds or len(bounds) != 2:
            logger.warning(
                "Internal COG tile_server %s has no usable bounds; skipping its "
                "footprint.",
                tile_server.id,
            )
            return None
        (south, west), (north, east) = bounds
        ring = [
            [west, south],
            [east, south],
            [east, north],
            [west, north],
            [west, south],
        ]
        geometry = {"type": "Polygon", "coordinates": [ring]}
        cls._warn_if_large("COG", tile_server.id, abs(east - west), abs(north - south))

        # TileServerLayer descriptor the consumer feeds to its layer builder.
        descriptor = {
            "id": tile_server.id,
            "name": tile_server.name,
            "type": tile_server.type,
            "kind": tile_server.kind,
            "internal": tile_server.internal,
            "uuid": str(tile_server.uuid) if tile_server.uuid else None,
            "url": tile_server.url,
            "attribution": tile_server.attribution,
            "tileOptions": tile_options,
            "uiOptions": tile_server.uiOptions or {},
        }

        properties = dict(common)
        properties.update(
            {
                "feature_id": None,
                "feature_type": "cog",
                "cog_url": cls._build_cog_url(tile_server, geoapi_base),
                "bounds": [west, south, east, north],
                "tile_layer": descriptor,
            }
        )
        return {"type": "Feature", "geometry": geometry, "properties": properties}

    @classmethod
    def _vector_footprint(cls, feature, geometry, vector_asset, common, geoapi_base):
        """Layer footprint for a PMTiles-vector upload: the feature bbox + a pointer
        to the upload's own PMTiles archive."""
        minx, miny, maxx, maxy = shapely.geometry.shape(geometry).bounds
        cls._warn_if_large("Vector", feature.id, abs(maxx - minx), abs(maxy - miny))
        properties = dict(common)
        properties.update(
            {
                "feature_id": feature.id,
                "feature_type": "vector",
                "pmtiles_url": f"{geoapi_base}/assets/{vector_asset.path}",
                "bounds": [minx, miny, maxx, maxy],
            }
        )
        return {"type": "Feature", "geometry": geometry, "properties": properties}

    @staticmethod
    def _warn_if_large(kind, obj_id, width_deg, height_deg):
        if max(width_deg, height_deg) > LARGE_EXTENT_WARN_DEG:
            logger.warning(
                "%s %s footprint extent %.2f x %.2f deg is unusually large "
                "(possible georef error); still included.",
                kind,
                obj_id,
                width_deg,
                height_deg,
            )
        else:
            logger.info(
                "%s %s footprint extent %.3f x %.3f deg.",
                kind,
                obj_id,
                width_deg,
                height_deg,
            )

    @staticmethod
    def _build_cog_url(tile_server, geoapi_base) -> str:
        """Pre-resolved TiTiler tile URL template for an internal COG.

        Mirrors the hazmapper frontend's resolveTileUrl: wrap the internal file
        path as ``file://...`` (URL-encoded) and append any render options. The
        ``{z}/{x}/{y}`` placeholders are left literal for the consumer.
        """
        file_url = "file://" + tile_server.url
        encoded = quote(file_url, safe="")
        url = (
            f"{geoapi_base}/tiles/cog/tiles/WebMercatorQuad/"
            f"{{z}}/{{x}}/{{y}}.png?url={encoded}"
        )
        render_options = (tile_server.uiOptions or {}).get("renderOptions") or {}
        for key, value in render_options.items():
            url += f"&{key}={quote(str(value), safe='')}"
        return url
