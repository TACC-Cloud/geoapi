import os
import uuid
import subprocess
import pathlib
from geoapi.celery_app import app
from geoapi.db import db_session


@app.task()
def convert_to_potree(projectId: int, featureId: int, filePath: str) -> None:
    """
    Use the potree converter to convert a LAS/LAZ file to potree format
    :param projectId: int
    :param featureId: int
    :param filePath: Local path to las/laz file
    :return: None
    """
    from geoapi.models import Feature, FeatureAsset

    asset_uuid = uuid.uuid4()
    asset_path = os.path.join("/assets", str(projectId), str(asset_uuid))
    pathlib.Path(asset_path).mkdir(parents=True, exist_ok=True)

    subprocess.run([
        "PotreeConverter",
        "-i",
        filePath,
        "-o",
        asset_path,
        "--generate-page",
        "index"
    ])

    f = db_session.query(Feature).get(featureId)
    properties = dict(f.properties)
    properties["point_cloud_file"] = asset_path

    fa = FeatureAsset(
        uuid=asset_uuid,
        asset_type="point_cloud",
        path=asset_path,
        feature=f,
    )
    f.assets.append(fa)
    db_session.commit()


if __name__== "__main__":
    convert_to_potree()