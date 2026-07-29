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
    """Turn selected published maps into GeoJSON features for tiling.

    Emits one GeoJSON feature per Hazmapper feature, plus one footprint polygon
    per internal COG (rasters are never tiled into this archive -- only their
    bounds, carrying a layer descriptor the consumer can use to load the real
    COG on demand). Every feature carries a small, stable, snake_case property
    set that WG-671 (Recon Portal) depends on.
    """

    @classmethod
    def build_features(
        cls, database_session, published_maps: List[PublishedMap]
    ) -> Tuple[List[dict], dict]:
        """Build the GeoJSON features and summary stats.

        :return: ``(features, stats)`` where ``features`` is a list of GeoJSON
            Feature dicts and ``stats`` has ``feature_count`` (DB features),
            ``cog_count`` (COG footprints), ``project_count`` and ``total``.
        """
        geoapi_base = get_deployed_geoapi_url()
        hazmapper_base = get_deployed_hazmapper_url()

        features: List[dict] = []
        feature_count = 0
        cog_count = 0

        for published in published_maps:
            project = published.project
            common = {
                "project_uuid": str(project.uuid),
                "project_name": project.name,
                "ds_project_id": published.designsafe_project_id,
                "ds_doi": published.designsafe_doi,
                "ds_project_url": DESIGNSAFE_PUBLISHED_BROWSER_URL.format(
                    designsafe_project_id=published.designsafe_project_id
                ),
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
                        "hazmapper_url": cls._hazmapper_url(
                            hazmapper_base, project.uuid, feature.id
                        ),
                        "has_assets": bool(feature.assets),
                        "created_date": (
                            feature.created_date.isoformat()
                            if feature.created_date
                            else None
                        ),
                    }
                )
                thumbnail_url = cls._thumbnail_url(feature, geoapi_base)
                if thumbnail_url:
                    properties["thumbnail_url"] = thumbnail_url

                features.append(
                    {"type": "Feature", "geometry": geometry, "properties": properties}
                )
                feature_count += 1

            # internal COG footprints (never the pixels -- just the outline + a
            # descriptor the consumer uses to instantiate the real tile layer)
            for tile_server in (
                database_session.query(TileServer)
                .filter(TileServer.project_id == project.id)
                .filter(TileServer.internal.is_(True))
                .filter(TileServer.kind == "cog")
                .all()
            ):
                footprint = cls._cog_footprint(
                    tile_server, common, hazmapper_base, geoapi_base, project.uuid
                )
                if footprint:
                    features.append(footprint)
                    cog_count += 1

        stats = {
            "feature_count": feature_count,
            "cog_count": cog_count,
            "project_count": len(published_maps),
            "total": len(features),
        }
        logger.info(
            "Public export built %s feature(s): %s DB features + %s COG footprints "
            "across %s project(s).",
            stats["total"],
            feature_count,
            cog_count,
            stats["project_count"],
        )
        return features, stats

    @staticmethod
    def _feature_type(feature) -> str:
        for asset in feature.assets:
            mapped = _ASSET_TYPE_TO_FEATURE_TYPE.get(asset.asset_type)
            if mapped:
                return mapped
        geometry_type = ((feature.geometry or {}).get("type") or "").lower()
        return "point" if "point" in geometry_type else "shape"

    @staticmethod
    def _thumbnail_url(feature, geoapi_base) -> Optional[str]:
        """URL of an image feature's thumbnail, if it has one.

        Image assets are stored as ``<uuid>.jpeg`` alongside a
        ``<uuid>.thumb.jpeg`` thumbnail (see FeaturesService.fromImage), and are
        served at ``{geoapi}/assets/{asset.path}``.
        """
        for asset in feature.assets:
            if (
                asset.asset_type == "image"
                and asset.path
                and asset.path.endswith(".jpeg")
            ):
                thumb_path = asset.path[: -len(".jpeg")] + ".thumb.jpeg"
                return f"{geoapi_base}/assets/{thumb_path}"
        return None

    @staticmethod
    def _hazmapper_url(hazmapper_base, project_uuid, feature_id=None) -> str:
        url = f"{hazmapper_base}/project-public/{project_uuid}"
        if feature_id is not None:
            url += f"?selectedFeature={feature_id}"
        return url

    @classmethod
    def _cog_footprint(
        cls, tile_server, common, hazmapper_base, geoapi_base, project_uuid
    ) -> Optional[dict]:
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
                "hazmapper_url": cls._hazmapper_url(hazmapper_base, project_uuid),
                "has_assets": True,
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
