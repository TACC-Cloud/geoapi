import time
from dataclasses import dataclass
from typing import Iterator, List, Optional

import requests

from geoapi.log import logging
from geoapi.models import Project
from geoapi.settings import settings

logger = logging.getLogger(__name__)

# DesignSafe publications API (public, unauthenticated). This is intentionally a
# module-level constant rather than a per-environment setting: "published" is a
# production DesignSafe curation act, and the maps embedded in a publication are
# tagged with the deployment that registered them (see below), so pointing at a
# single publications host and filtering by deployment is what keeps each geoapi
# tier scoped to its own maps. Overridable in tests.
DESIGNSAFE_PUBLICATIONS_API = "https://www.designsafe-ci.org/api/publications/v2"

# Page size when walking the publications list.
PUBLICATIONS_PAGE_LIMIT = 100

# HTTP timeout for a single DesignSafe request.
REQUEST_TIMEOUT_SECONDS = 30


@dataclass
class PublishedMap:
    """A Hazmapper map that belongs to a published DesignSafe project *and* to
    this geoapi deployment.

    ``project`` is the local geoapi Project (already confirmed public); the
    remaining fields carry the DesignSafe publication context needed to enrich
    exported features.
    """

    project: Project
    map_uuid: str
    map_name: Optional[str]
    map_path: Optional[str]
    designsafe_project_id: str  # PRJ-####
    designsafe_project_title: Optional[str]
    designsafe_doi: Optional[str]


class PublishedMapsService:
    """Select the Hazmapper maps that back public, published DesignSafe projects
    for the current deployment.

    The traversal mirrors the qgis plugin's discovery script
    (``hazmapper-qgis-plugin/scripts/designsafe_hazmapper_discovery.py``): start
    from the DesignSafe publications API, and for each publication read the
    ``baseProject.hazmapperMaps`` it embeds. Each embedded map is tagged with the
    ``deployment`` (the ``APP_ENV`` of the geoapi that registered it -- see
    ``custom/designsafe/project.py``), which is how a single publication can
    reference maps on more than one tier.

    A map is selected only when all three conditions hold:
      1. published  -- it appears in a DesignSafe publication
      2. this tier  -- ``deployment == settings.APP_ENV``
      3. public     -- the local Project joined by ``uuid`` has ``public = True``

    A map that matches this deployment but whose local project is missing or not
    public is logged and skipped, not raised -- one bad map must not sink the
    nightly run.
    """

    # HTTP entry points are isolated here so tests can patch them without a
    # network round-trip.
    publications_api = DESIGNSAFE_PUBLICATIONS_API

    # Politeness delay between per-project detail requests. Set to 0 in tests.
    inter_request_sleep_seconds = 0.1

    @classmethod
    def _get_json(cls, url: str) -> dict:
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()

    @classmethod
    def _iter_published_projects(cls) -> Iterator[dict]:
        """Yield every published project (paged) from the publications list."""
        offset = 0
        while True:
            data = cls._get_json(
                f"{cls.publications_api}?offset={offset}&limit={PUBLICATIONS_PAGE_LIMIT}"
            )
            projects = data.get("result", [])
            if not projects:
                return
            for project in projects:
                yield project
            # a short page means we've reached the end
            if len(projects) < PUBLICATIONS_PAGE_LIMIT:
                return
            offset += PUBLICATIONS_PAGE_LIMIT

    @classmethod
    def _fetch_base_project(cls, designsafe_project_id: str) -> dict:
        """Return the ``baseProject`` block for a single publication.

        Carries both the embedded ``hazmapperMaps`` and the publication ``dois``.
        """
        detail = cls._get_json(f"{cls.publications_api}/{designsafe_project_id}")
        return detail.get("baseProject") or {}

    @classmethod
    def get_published_maps(
        cls, database_session
    ) -> List[PublishedMap]:
        """Resolve the published, this-deployment, public maps to local Projects.

        :param database_session: SQLAlchemy session bound to this deployment's DB
        :return: selected maps (may be empty -- e.g. a tier with no published maps)
        """
        deployment = settings.APP_ENV
        selected: List[PublishedMap] = []
        seen_uuids: set[str] = set()
        deployment_matched = 0

        for project in cls._iter_published_projects():
            designsafe_project_id = project.get("projectId")
            if not designsafe_project_id:
                continue
            designsafe_title = project.get("title")

            base_project = cls._fetch_base_project(designsafe_project_id)
            dois = base_project.get("dois") or []
            designsafe_doi = dois[0] if dois else None

            for hazmapper_map in base_project.get("hazmapperMaps") or []:
                map_uuid = hazmapper_map.get("uuid")
                if not map_uuid:
                    continue

                # Condition 2: only maps registered by *this* geoapi deployment. A map
                # tagged for another tier lives in another tier's DB; skip quietly.
                if hazmapper_map.get("deployment") != deployment:
                    continue

                deployment_matched += 1
                if map_uuid in seen_uuids:
                    continue

                # Condition 3: the map must resolve to a local, public project.
                local_project = (
                    database_session.query(Project)
                    .filter(Project.uuid == map_uuid)
                    .one_or_none()
                )
                if local_project is None:
                    logger.warning(
                        "Published map tagged for this deployment label is not in "
                        "this database; skipping. This is expected when the label is "
                        "shared across instances (e.g. another 'local'/'dev'). "
                        f"deployment:{deployment} designsafe_project:{designsafe_project_id} "
                        f"map_uuid:{map_uuid}"
                    )
                    continue
                if not local_project.public:
                    # Published on DesignSafe but toggled non-public in Hazmapper.
                    # Log at error level (an inconsistency worth noticing) but do
                    # not raise -- just exclude this one map.
                    logger.error(
                        "Published DesignSafe map resolves to a non-public project; "
                        "excluding it from the public archive. "
                        f"deployment:{deployment} designsafe_project:{designsafe_project_id} "
                        f"map_uuid:{map_uuid} project_id:{local_project.id}"
                    )
                    continue

                seen_uuids.add(map_uuid)
                selected.append(
                    PublishedMap(
                        project=local_project,
                        map_uuid=map_uuid,
                        map_name=hazmapper_map.get("name"),
                        map_path=hazmapper_map.get("path"),
                        designsafe_project_id=designsafe_project_id,
                        designsafe_project_title=designsafe_title,
                        designsafe_doi=designsafe_doi,
                    )
                )

            if cls.inter_request_sleep_seconds:
                time.sleep(cls.inter_request_sleep_seconds)

        logger.info(
            f"Selected {len(selected)} published, public map(s) for deployment "
            f"'{deployment}' (out of {deployment_matched} deployment-matched "
            "published map(s))."
        )
        return selected
