import json
from geoapi.log import logger
from geoapi.custom.designsafe.default_basemap_layers import default_layers
from geoapi.models import User, Project
import requests

DESIGNSAFE_URL = 'https://www.designsafe-ci.org/'  # 'https://designsafeci-dev.tacc.utexas.edu/';

DEPLOYMENT = 'local'  # TODO


def on_project_creation(database_session, user: User, project: Project):
    try:
        deployment = DEPLOYMENT
        file_content = json.dumps({"uuid": str(project.uuid), "deployment": deployment})
        file_name = project.system_file + ".hazmapper"
        from geoapi.utils.agave import AgaveUtils
        tapis = AgaveUtils(jwt=user.jwt)
        tapis.create_file(system_id=project.system_id,
                          system_path=project.system_path,
                          file_name=file_name,
                          file_content=file_content)
    except Exception:
        logger.exception(f"Problem creating .hazmapper file for user:{user.username}"
                         f"project:{project.id} project_uuid:{project.uuid} ")

    try:
        from geoapi.services.features import FeaturesService
        for layer in default_layers:
            FeaturesService.addTileServer(database_session=database_session,
                                          projectId=project.id,
                                          data=layer)

    except Exception:
        logger.exception(f"Problem adding two default layers for user:{user.username}"
                         f"project:{project.id} project_uuid:{project.uuid} ")

    try:
        # add metadata to DS projects (i.e. only when system_id starts with "project-"
        if project.system_id.startswith("project-"):
            update_designsafe_project_hazmapper_metadata(user, project, add_project=True)
    except Exception:
        logger.exception(f"Problem adding metadata for user:{user.username}"
                         f"project:{project.id} project_uuid:{project.uuid} ")


def on_project_deletion(user: User, project: Project):
    file_path = project.system_file + ".hazmapper"

    try:
        from geoapi.utils.agave import AgaveUtils
        tapis = AgaveUtils(jwt=user.jwt)
        tapis.delete_file(system_id=project.system_id,
                          file_path=file_path)
    except Exception:
        logger.exception(f"Problem removing .hazmapper file for user:{user.username}"
                         f"project:{project.id} project_uuid:{project.uuid}"
                         f"system_id:{project.system_id} file_path:{file_path}")

    try:
        # remove metadata for DS projects (i.e. only when system_id starts with "project-"
        if project.system_id.startswith("project-"):
            update_designsafe_project_hazmapper_metadata(user, project, add_project=False)
    except Exception:
        logger.exception(f"Problem removing metadata for user:{user.username}"
                         f"project:{project.id} project_uuid:{project.uuid} ")


def update_designsafe_project_hazmapper_metadata(user: User, project: Project, add_project: bool):
    designsafe_uuid = project.system_id[len("project-"):]

    client = requests.Session()
    client.headers.update({'X-JWT-Assertion-designsafe': user.jwt})

    response = client.get(DESIGNSAFE_URL + f"api/projects{designsafe_uuid}")
    response.raise_for_status()

    current_metadata = response.json()
    all_maps = []
    if "hazmapper" in current_metadata["value"]:
        # remove this project from the map list as we will update (or delete) it
        all_maps = [e for e in current_metadata['value']['hazmapperMaps'] if e['uuid'] != project.uuid]

    if add_project:
        new_map_entry = {"name": project.name,
                         "uuid": project.uuid,
                         "path": project.system_path,
                         "deployment": DEPLOYMENT}
        all_maps.append(new_map_entry)
    response = client.post(DESIGNSAFE_URL + f"api/projects{designsafe_uuid}", json={"hazmapperMaps": all_maps})
    response.raise_for_status()
