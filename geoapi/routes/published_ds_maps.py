from litestar import Controller, get
from litestar.response import Response

from geoapi.log import logging
from geoapi.tasks.published_ds_maps import read_manifest

logger = logging.getLogger(__name__)


class PublishedDsMapsController(Controller):
    """Unauthenticated discovery endpoint for the published DesignSafe maps archive.

    It just serves the sidecar ``manifest.json`` written by the nightly
    task. It never streams the archive as nginx serves the .pmtiles directly).
    """

    path = "/designsafe"
    tags = ["public"]

    @get("/published-maps/pmtiles")
    async def get_published_maps_pmtiles(self) -> Response:
        """Return the manifest for the current combined public PMTiles archive of
        published DesignSafe project maps (url + metadata), or 404 if none has
        been generated yet.
        """
        manifest = read_manifest()
        if manifest is None:
            return Response(
                content={"detail": "No published-maps archive is available yet."},
                status_code=404,
            )
        return Response(content=manifest, status_code=200)
