import logging
import uuid
from unittest.mock import patch

from geoapi.models import Project
from geoapi.custom.designsafe.published_maps import PublishedMapsService
from geoapi.settings import settings


def _make_project(db_session, name, public):
    """Create + commit a project and return it (uuid is auto-generated)."""
    project = Project(name=name, description=name, tenant_id="test", public=public)
    db_session.add(project)
    db_session.commit()
    return project


def _fake_designsafe_api(pages, details):
    """Build a _get_json replacement that routes by URL.

    :param pages: dict of offset -> list result page
    :param details: dict of PRJ id -> hazmapperMaps list
    """

    def _get_json(url):
        if "/publications/v2?" in url or url.endswith("/publications/v2"):
            # extract offset from the query string
            offset = int(url.split("offset=")[1].split("&")[0])
            return {"result": pages.get(offset, [])}
        designsafe_project_id = url.rsplit("/", 1)[1]
        return {
            "baseProject": {"hazmapperMaps": details.get(designsafe_project_id, [])}
        }

    return _get_json


def test_get_published_maps_selects_only_matching_maps_and_logs_exclusions(
    db_session, caplog
):
    """A map is selected only if it passes all three conditions -- published,
    deployment == APP_ENV, and the local project is public -- and the two
    inconsistency paths (non-public, not-in-DB) are logged."""
    this_deployment = settings.APP_ENV

    public_project = _make_project(db_session, "public-map", public=True)
    private_project = _make_project(db_session, "private-map", public=False)
    missing_uuid = str(uuid.uuid4())

    pages = {
        0: [
            {"projectId": "PRJ-1", "title": "Published One"},
            {"projectId": "PRJ-2", "title": "Published Two"},
            {"projectId": "PRJ-3", "title": "Published Three"},
            {"projectId": "PRJ-4", "title": "Published Four"},
        ]
    }
    details = {
        # selected: published + this deployment + public
        "PRJ-1": [
            {
                "uuid": str(public_project.uuid),
                "name": "Public Map",
                "path": "/",
                "deployment": this_deployment,
            }
        ],
        # excluded: resolves to a non-public project -> error logged
        "PRJ-2": [{"uuid": str(private_project.uuid), "deployment": this_deployment}],
        # excluded: registered by a different deployment tier
        "PRJ-3": [{"uuid": str(public_project.uuid), "deployment": "some-other-tier"}],
        # excluded: this deployment, but no such project in the DB -> warning
        "PRJ-4": [{"uuid": missing_uuid, "deployment": this_deployment}],
    }

    with patch.object(
        PublishedMapsService,
        "_get_json",
        side_effect=_fake_designsafe_api(pages, details),
    ), patch.object(
        PublishedMapsService, "inter_request_sleep_seconds", 0
    ), caplog.at_level(
        logging.WARNING
    ):
        selected = PublishedMapsService.get_published_maps(db_session)

    # only the public, this-deployment map survives all three conditions
    assert len(selected) == 1
    result = selected[0]
    assert result.project.id == public_project.id
    assert result.map_uuid == str(public_project.uuid)
    assert result.map_name == "Public Map"
    assert result.designsafe_project_id == "PRJ-1"
    assert result.designsafe_project_title == "Published One"

    # the non-public inconsistency is logged at error level (not raised)
    assert any(
        record.levelno == logging.ERROR and "non-public" in record.getMessage()
        for record in caplog.records
    )
    # the missing map is logged at warning level
    assert any(
        record.levelno == logging.WARNING and missing_uuid in record.getMessage()
        for record in caplog.records
    )


def test_selector_returns_empty_when_no_deployment_matches(db_session):
    """A tier with no published maps of its own yields an empty selection."""
    public_project = _make_project(db_session, "public-map", public=True)

    pages = {0: [{"projectId": "PRJ-1", "title": "Published One"}]}
    details = {
        "PRJ-1": [
            {"uuid": str(public_project.uuid), "deployment": "a-different-deployment"}
        ]
    }

    with patch.object(
        PublishedMapsService,
        "_get_json",
        side_effect=_fake_designsafe_api(pages, details),
    ), patch.object(PublishedMapsService, "inter_request_sleep_seconds", 0):
        selected = PublishedMapsService.get_published_maps(db_session)

    assert selected == []
