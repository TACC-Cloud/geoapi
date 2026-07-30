import json
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

COG_LARGE_EXTENT_WARN_DEG = 30

# asset_type (FeatureAsset) -> feature_type carried in the archive. Types not
# listed here fall through to a geometry-based point/shape classification (this
# covers plain geometry features and PMTiles "vector" assets, whose own detail
# lives in a separate archive).
_ASSET_TYPE_TO_FEATURE_TYPE = {
    "image": "image",
    "video": "video",
    "point_cloud": "point_cloud",
    "streetview": "streetview",
    "questionnaire": "questionnaire",
}


class PublishedMapsExportService:
    """Turn selected published maps into GeoJSON for the public archive.

    Emits per-Hazmapper-feature dicts for the tiled PMTiles archive, plus
    internal-COG footprint polygons for a companion cogs.geojson to be rendered
    client-side. Every feature carries a property set that Recon Portal uses.
    """

    @classmethod
    def build_features(
        cls, database_session, published_maps: List[PublishedMap]
    ) -> Tuple[List[dict], List[dict], dict]:
        """Build the tiled features and the COG footprints.

        :return: ``(features, cog_features, stats)``. ``features`` are the
            per-Hazmapper-feature dicts tiled into the PMTiles archive.
            ``cog_features`` are internal-COG footprint polygons written to a
            companion cogs.geojson and rendered client-side (not tiled -- see
            _cog_footprint). ``stats`` has ``feature_count`` (tiled),
            ``cog_count``, ``project_count`` and ``total`` (tiled).
        """
        geoapi_base = get_deployed_geoapi_url()
        hazmapper_base = get_deployed_hazmapper_url()

        features: List[dict] = []
        cog_features: List[dict] = []
        feature_count = 0
        cog_count = 0

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

            # regular Hazmapper features
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

            # internal COG footprints -> companion cogs.geojson (rendered
            # client-side, not tiled), each carrying a layer descriptor + tile URL
            for tile_server in (
                database_session.query(TileServer)
                .filter(TileServer.project_id == project.id)
                .filter(TileServer.internal.is_(True))
                .filter(TileServer.kind == "cog")
                .all()
            ):
                footprint = cls._cog_footprint(tile_server, common, geoapi_base)
                if footprint:
                    cog_features.append(footprint)
                    cog_count += 1

        stats = {
            "feature_count": feature_count,
            "cog_count": cog_count,
            "project_count": len(published_maps),
            "total": len(features),
        }
        logger.info(
            "Public export built %s tiled feature(s) + %s COG footprint(s) "
            "across %s project(s).",
            feature_count,
            cog_count,
            stats["project_count"],
        )
        return features, cog_features, stats

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
        # Filled footprint polygon. COGs go into a companion cogs.geojson
        ring = [
            [west, south],
            [east, south],
            [east, north],
            [west, north],
            [west, south],
        ]
        geometry = {"type": "Polygon", "coordinates": [ring]}
        width_deg, height_deg = abs(east - west), abs(north - south)
        if max(width_deg, height_deg) > COG_LARGE_EXTENT_WARN_DEG:
            logger.warning(
                "COG %s footprint extent %.2f x %.2f deg is unusually large "
                "(possible georef error); still included.",
                tile_server.id,
                width_deg,
                height_deg,
            )
        else:
            logger.info(
                "COG %s footprint extent %.3f x %.3f deg.",
                tile_server.id,
                width_deg,
                height_deg,
            )

        ui_options = tile_server.uiOptions or {}
        render_options = ui_options.get("renderOptions") or {}

        # Field-for-field mirror of hazmapper's TileServerLayer, JSON-encoded so
        # the consumer can reconstruct the layer with no translation shim. (Vector
        # tile attributes must be scalars, so this rides as a string; the flat
        # fields below are convenience duplicates for quick styling/labeling.)
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
            "uiOptions": ui_options,
        }

        properties = dict(common)
        properties.update(
            {
                "feature_id": None,
                "feature_type": "cog",
                "tile_server_id": tile_server.id,
                "layer_name": tile_server.name,
                "layer_type": tile_server.type,
                "min_zoom": tile_options.get("minZoom"),
                "max_zoom": tile_options.get("maxZoom"),
                "max_native_zoom": tile_options.get("maxNativeZoom"),
                "attribution": tile_server.attribution,
                "opacity": ui_options.get("opacity"),
                "colormap_name": render_options.get("colormap_name"),
                "cog_url": cls._build_cog_url(tile_server, geoapi_base),
                "tile_layer": json.dumps(descriptor),
            }
        )
        return {"type": "Feature", "geometry": geometry, "properties": properties}

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
