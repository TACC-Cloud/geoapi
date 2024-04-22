from geoapi.celery_app import app
from geoapi.utils.assets import get_project_asset_dir
from geoapi.log import logger
import shutil


@app.task()
def remove_project_assets(project_id):
    """
    Remove all assets associated with a project.

    The directory containing that project's assets will be deleted.

    """
    logger.info(f"Deleting project:{project_id} started")
    assets_folder = get_project_asset_dir(project_id)
    try:
        shutil.rmtree(assets_folder)
        logger.info(f"Deleting project:{project_id} finished")
    except FileNotFoundError:
        logger.info(f"Deleting project:{project_id} completed but caught FileNotFoundError")
        pass
