import os
import subprocess
import uuid
from geoapi.celery_app import app
from utils.agave import AgaveUtils

@app.task()
def convert_to_potree(projectID: int, filePath: str, cOptions: str = None) -> None:
    """
    Use the potree converter to convert a LAS/LAZ file to potree format
    :param filePath: Local path to las/laz file
    :return:
    """
    asset_uuid = uuid.uuid4()
    asset_path = os.path.join("/assets", str(projectID), str(asset_uuid))
    subprocess.run([
        "PotreeConverter",
        "-i",
        filePath,
        "-o",
        asset_path
    ])


if __name__== "__main__":
    convert_to_potree()