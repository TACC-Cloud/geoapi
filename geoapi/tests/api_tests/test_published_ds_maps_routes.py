from unittest.mock import patch

ROUTE = "/designsafe/published-maps/pmtiles"


def test_get_manifest_returns_200_when_present(test_client):
    manifest = {
        "url": "https://example.org/assets/public/published_ds_maps_x.pmtiles",
        "generated_at": "2026-07-24T03:00:00+00:00",
        "feature_count": 5,
        "project_count": 2,
        "bounds": [-98.0, 30.0, -96.0, 31.0],
        "zoom_min": 6,
        "zoom_max": 16,
        "schema_version": 1,
    }
    # unauthenticated (guest) access, no token
    with patch("geoapi.routes.published_ds_maps.read_manifest", return_value=manifest):
        resp = test_client.get(ROUTE)
    assert resp.status_code == 200
    assert resp.json() == manifest


def test_get_manifest_returns_404_when_missing(test_client):
    with patch("geoapi.routes.published_ds_maps.read_manifest", return_value=None):
        resp = test_client.get(ROUTE)
    assert resp.status_code == 404
    assert "detail" in resp.json()
