from geoapi.utils.agave import AgaveUtils
import json


def on_project_creation(user, project):
    deployment = 'local' # TODO
    file_content = json.dumps({"uuid": project.uuid, "deployment": deployment})
    file_name = project.system_file + ".hazmapper"

    tapis = AgaveUtils(jwt=user.jwt, tenant=user.tenant_id)
    tapis.create_file(system_id=project.system_id,
                      system_path=project.system_path,
                      file_name=file_name,
                      file_content=file_content)


def on_project_deletion():
    pass
