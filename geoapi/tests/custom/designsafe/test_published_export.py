import uuid

from geoalchemy2.shape import from_shape
from shapely.geometry import Point, box

from geoapi.models import Feature, FeatureAsset, Project, TileServer
from geoapi.custom.designsafe.published_export import PublishedMapsExportService
from geoapi.custom.designsafe.published_maps import PublishedMap


def _project(db_session):
    project = Project(name="pub", description="pub", tenant_id="test", public=True)
    db_session.add(project)
    db_session.commit()
    return project


def _point_feature(db_session, project):
    feature = Feature(project_id=project.id, properties={})
    feature.the_geom = from_shape(Point(-97.0, 30.0), srid=4326)
    db_session.add(feature)
    db_session.commit()
    return feature


def _image_feature(db_session, project):
    feature = Feature(project_id=project.id, properties={})
    feature.the_geom = from_shape(Point(-96.0, 31.0), srid=4326)
    asset_uuid = uuid.uuid4()
    asset = FeatureAsset(
        uuid=asset_uuid,
        asset_type="image",
        path=f"{project.id}/{asset_uuid}.jpeg",
        feature=feature,
    )
    feature.assets.append(asset)
    db_session.add(feature)
    db_session.commit()
    return feature


def _vector_feature(db_session, project):
    feature = Feature(project_id=project.id, properties={})
    feature.the_geom = from_shape(box(-99.0, 29.0, -98.0, 30.0), srid=4326)
    asset_uuid = uuid.uuid4()
    asset = FeatureAsset(
        uuid=asset_uuid,
        asset_type="vector",
        path=f"{project.id}/{asset_uuid}.pmtiles",
        feature=feature,
    )
    feature.assets.append(asset)
    db_session.add(feature)
    db_session.commit()
    return feature


def _cog_tile_server(db_session, project):
    ts = TileServer(
        project_id=project.id,
        name="my-cog",
        type="xyz",
        kind="cog",
        internal=True,
        uuid=uuid.uuid4(),
        url=f"/assets/{project.id}/{uuid.uuid4()}.cog.tif",
        attribution="TACC",
        tileOptions={
            "minZoom": 0,
            "maxZoom": 22,
            "maxNativeZoom": 22,
            "bounds": [[30.0, -97.0], [31.0, -96.0]],
            "renderOptions": {"colormap_name": "terrain"},
        },
        uiOptions={"opacity": 1, "renderOptions": {"colormap_name": "terrain"}},
    )
    db_session.add(ts)
    db_session.commit()
    return ts


def _published(project, doi="10.17603/ds2-test"):
    return PublishedMap(
        project=project,
        map_uuid=str(project.uuid),
        map_name="My Map",
        map_path="/",
        designsafe_project_id="PRJ-1",
        designsafe_project_title="Published One",
        designsafe_doi=doi,
    )


def test_build_features_tiles_markers_and_lists_layer_footprints(db_session):
    project = _project(db_session)
    point = _point_feature(db_session, project)
    image = _image_feature(db_session, project)
    vector = _vector_feature(db_session, project)
    _cog_tile_server(db_session, project)

    features, layer_features, stats = PublishedMapsExportService.build_features(
        db_session, [_published(project)]
    )

    # markers are tiled; COG + vector become layer footprints (companion geojson)
    assert stats == {
        "feature_count": 2,
        "cog_count": 1,
        "vector_count": 1,
        "project_count": 1,
        "total": 2,
    }
    assert len(features) == 2
    assert len(layer_features) == 2

    by_type = {}
    for f in features:
        by_type.setdefault(f["properties"]["feature_type"], []).append(f)
    layers_by_type = {}
    for f in layer_features:
        layers_by_type.setdefault(f["properties"]["feature_type"], []).append(f)

    # shared project context on everything (tiled + layer footprints)
    for f in features + layer_features:
        props = f["properties"]
        assert props["hazmapper_project_uuid"] == str(project.uuid)
        assert props["hazmapper_project_name"] == "pub"
        assert props["ds_project_name"] == "Published One"
        assert "designsafe.storage.published/PRJ-1" in props["ds_project_url"]
        assert props["hazmapper_url"].endswith(f"/project-public/{project.uuid}")
        assert "selectedFeature" not in props["hazmapper_url"]
        for gone in (
            "project_uuid",
            "ds_project_id",
            "ds_doi",
            "has_assets",
            "created_date",
        ):
            assert gone not in props

    assert by_type["point"][0]["properties"]["feature_id"] == point.id
    assert "thumbnail_url" not in by_type["point"][0]["properties"]
    assert by_type["image"][0]["properties"]["feature_id"] == image.id

    # COG footprint: filled polygon + tile url + descriptor object + bounds
    cog = layers_by_type["cog"][0]
    assert cog["geometry"]["type"] == "Polygon"
    assert cog["properties"]["feature_id"] is None
    assert len(cog["properties"]["bounds"]) == 4
    cog_url = cog["properties"]["cog_url"]
    assert "/tiles/cog/tiles/WebMercatorQuad/{z}/{x}/{y}.png?url=" in cog_url
    assert "colormap_name=terrain" in cog_url
    descriptor = cog["properties"]["tile_layer"]
    assert descriptor["internal"] is True
    assert descriptor["kind"] == "cog"
    assert descriptor["tileOptions"]["maxZoom"] == 22

    # vector footprint: bbox polygon + pointer to its own PMTiles
    vec = layers_by_type["vector"][0]
    assert vec["geometry"]["type"] == "Polygon"
    assert vec["properties"]["feature_id"] == vector.id
    assert vec["properties"]["pmtiles_url"].endswith(".pmtiles")
    assert "/assets/" in vec["properties"]["pmtiles_url"]
    assert len(vec["properties"]["bounds"]) == 4


def test_external_tile_layers_are_not_exported(db_session):
    project = _project(db_session)
    # an external (user-attached) layer -- must be excluded
    external = TileServer(
        project_id=project.id,
        name="external-basemap",
        type="tms",
        kind=None,
        internal=False,
        url="https://example.com/{z}/{x}/{y}.png",
        attribution="someone else",
        tileOptions={"bounds": [[30.0, -97.0], [31.0, -96.0]]},
        uiOptions={},
    )
    db_session.add(external)
    db_session.commit()

    features, layer_features, stats = PublishedMapsExportService.build_features(
        db_session, [_published(project)]
    )

    assert stats["cog_count"] == 0
    assert stats["vector_count"] == 0
    assert features == []
    assert layer_features == []
