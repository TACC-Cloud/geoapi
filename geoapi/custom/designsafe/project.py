import json
import os
from geoapi.log import logger
from geoapi.settings import settings
from geoapi.custom.designsafe.default_basemap_layers import default_layers
from geoapi.models import User, Project

import requests


def on_project_creation(database_session, user: User, project: Project):
    try:
        logger.debug(f"Creating .hazmapper file for user:{user.username}"
                     f" project:{project.id} project_uuid:{project.uuid} ")
        deployment = os.getenv("APP_ENV")
        file_content = json.dumps({"uuid": str(project.uuid), "deployment": deployment})
        file_name = f"{project.system_file}.hazmapper"
        from geoapi.utils.agave import AgaveUtils
        tapis = AgaveUtils(user)
        tapis.create_file(system_id=project.system_id,
                          system_path=project.system_path,
                          file_name=file_name,
                          file_content=file_content)
    except Exception:
        logger.exception(f"Problem creating .hazmapper file for user:{user.username}"
                         f" project:{project.id} project_uuid:{project.uuid} ")

    try:
        logger.debug(f"Adding two default layers for user:{user.username}"
                     f" project:{project.id} project_uuid:{project.uuid} ")
        from geoapi.services.features import FeaturesService
        for layer in default_layers:
            FeaturesService.addTileServer(database_session=database_session,
                                          projectId=project.id,
                                          data=layer)

    except Exception:
        logger.exception(f"Problem adding two default layers for user:{user.username}"
                         f" project:{project.id} project_uuid:{project.uuid} ")

    try:
        # add metadata to DS projects (i.e. only when system_id starts with "project-"
        if project.system_id.startswith("project-"):
            logger.debug(f"Adding metadata for user:{user.username}"
                         f" project:{project.id} project_uuid:{project.uuid} ")
            update_designsafe_project_hazmapper_metadata(user, project, add_project=True)
    except Exception:
        logger.exception(f"Problem adding metadata for user:{user.username}"
                         f" project:{project.id} project_uuid:{project.uuid} ")


def on_project_deletion(user: User, project: Project):
    file_path = f"{project.system_path}/{project.system_file}.hazmapper"

    try:
        logger.debug(f"Removing .hazmapper file for user:{user.username}"
                     f" during deletion of project:{project.id} project_uuid:{project.uuid}"
                     f"system_id:{project.system_id} file_path:{file_path}")
        from geoapi.utils.agave import AgaveUtils
        tapis = AgaveUtils(user)
        tapis.delete_file(system_id=project.system_id,
                          file_path=file_path)
    except Exception:
        logger.exception(f"Problem removing .hazmapper file for user:{user.username}"
                         f"during deletion of project:{project.id} project_uuid:{project.uuid}"
                         f"system_id:{project.system_id} file_path:{file_path}")

    try:
        # remove metadata for DS projects (i.e. only when system_id starts with "project-"
        if project.system_id.startswith("project-"):
            logger.debug(f"Removing metadata for user:{user.username}"
                         f" during deletion of project:{project.id} project_uuid:{project.uuid} ")
            update_designsafe_project_hazmapper_metadata(user, project, add_project=False)
    except Exception:
        logger.exception(f"Problem removing metadata for user:{user.username}"
                         f" during deletion of project:{project.id} project_uuid:{project.uuid} ")


def update_designsafe_project_hazmapper_metadata(user: User, project: Project, add_project: bool):
    designsafe_uuid = project.system_id[len("project-"):]

    client = requests.Session()
    client.headers.update({'X-JWT-Assertion-designsafe': user.jwt})

    response = client.get(settings.DESIGNSAFE_URL + f"/api/projects/v2/{designsafe_uuid}/")
    response.raise_for_status()

    current_metadata = response.json()
    all_maps = []
    logger.debug(f"Current metadata for DesignSafe_project:{designsafe_uuid}: {current_metadata}")
    if "hazmapperMaps" in current_metadata["baseProject"]["value"]:
        # remove this project from the map list as we will update (or delete) it
        all_maps = [e for e in current_metadata["baseProject"]['value']['hazmapperMaps'] if e['uuid'] != str(project.uuid)]

    if add_project:
        new_map_entry = {"name": project.name,
                         "uuid": str(project.uuid),
                         "path": project.system_path,
                         "deployment": os.getenv("APP_ENV")}
        all_maps.append(new_map_entry)
    logger.debug(f"Updated metadata for DesignSafe_project:{designsafe_uuid}: {all_maps}")
    response = client.patch(settings.DESIGNSAFE_URL + f"/api/projects/v2/{designsafe_uuid}/",
                           json={"patchMetadata": {"hazmapperMaps": all_maps}},
                           headers={'X-Requested-With': 'XMLHttpRequest'})
    response.raise_for_status()
