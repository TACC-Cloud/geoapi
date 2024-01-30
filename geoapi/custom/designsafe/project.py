import json
from geoapi.log import logger


def on_project_creation(user, project):
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
        logger.exception(f"Problem running on_project_creation steps for user:{user.username}"
                         f"project:{project.id} project_uuid:{project.uuid} ")


def on_project_deletion(user, project):
    try:
        from geoapi.utils.agave import AgaveUtils
        tapis = AgaveUtils(jwt=user.jwt)
        tapis.delete_file(system_id=project.system_id,
                          file_path=project.system_file)
    except Exception:
        logger.exception(f"Problem running on_project_deletion steps for user:{user.username}"
                         f"project:{project.id} project_uuid:{project.uuid} ")
