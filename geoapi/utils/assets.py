import os
from pathlib import Path
import glob
import shutil
from geoapi.settings import settings


def get_temp_dir() -> Path:
    """
    Get temp dir for downloading files etc.

    Relying on /tmp is problematic as there might not be enough space,
    while we know /assets has lots of space.
    """
    temp_dir = Path(settings.ASSETS_BASE_DIR) / "tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def make_project_asset_dir(projectId: int) -> str:
    """
    Creates a directory for a projects' assets in the ASSETS_BASE_DIR location
    :param projectId: int
    :return:
    """
    base_filepath = os.path.join(settings.ASSETS_BASE_DIR, str(projectId))
    Path(base_filepath).mkdir(parents=True, exist_ok=True)
    return base_filepath


def get_project_asset_dir(projectId: int) -> str:
    """
    Get project's asset directory
    :param projectId: int
    :return: string: asset directory
    """
    return os.path.join(settings.ASSETS_BASE_DIR, str(projectId))


def get_asset_path(*relative_paths) -> str:
    """
    Join asset directory with relative paths to get absolute path to assets
    :param relative_paths: str
    :return: string: absolute path to asset
    """
    return os.path.join(settings.ASSETS_BASE_DIR, *relative_paths)


def get_asset_relative_path(path: str) -> str:
    """
    Get path which is relative to asset directory

    If path is "/asset_dir/1/something.txt", then return
    "1/something.txt"

    :param path: str
    :return: string: relative path
    """
    return os.path.relpath(path, start=settings.ASSETS_BASE_DIR)


def delete_assets(projectId: int, uuid: str):
    """
    Delete project assets related to a single feature

    :param projectId: int
    :param uuid: str
    :return:
    """
    for asset_file in glob.glob(
        "{}/*{}*".format(get_project_asset_dir(projectId), uuid)
    ):
        if os.path.isfile(asset_file):
            os.remove(asset_file)
        else:
            shutil.rmtree(asset_file)
