import json
from geoapi.log import logger
from geoapi.services.features import FeaturesService
from geoapi.custom.designsafe.default_basemap_layers import default_layers


def on_project_creation(database_session, user, project):
    try:
        deployment = 'local'  # TODO
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
        for layer in default_layers:
            FeaturesService.addTileServer(database_session=database_session,
                                          projectId=project.id,
                                          data=layer)

    except Exception:
        logger.exception(f"Problem adding two default layers for user:{user.username}"
                         f"project:{project.id} project_uuid:{project.uuid} ")

    try:
        # add metadata
        pass
    except Exception:
        logger.exception(f"Problem adding metadata for user:{user.username}"
                         f"project:{project.id} project_uuid:{project.uuid} ")

def on_project_deletion(user, project):
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
        # remove metadata
        pass
    except Exception:
        logger.exception(f"Problem removing metadata for user:{user.username}"
                         f"project:{project.id} project_uuid:{project.uuid} ")