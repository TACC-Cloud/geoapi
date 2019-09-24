import os
import pathlib
from geoapi.settings import settings

def make_asset_dir(projectId: int) -> str:
    """
    Creates a directory for assets in the ASSETS_BASE_DIR location
    :param projectId: int
    :return:
    """
    base_filepath = os.path.join(settings.ASSETS_BASE_DIR, str(projectId))
    pathlib.Path(base_filepath).mkdir(parents=True, exist_ok=True)
    return base_filepath

def get_asset_dir(projectId: int) -> str:
    """
    Get project's asset directory
    :param projectId: int
    :return: string: asset directory
    """
    return os.path.join(settings.ASSETS_BASE_DIR, str(projectId))
