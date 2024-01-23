import json


def on_project_creation(user, project):
    deployment = 'local'  # TODO
    file_content = json.dumps({"uuid": str(project.uuid), "deployment": deployment})
    file_name = project.system_file + ".hazmapper"

    from geoapi.utils.agave import AgaveUtils
    tapis = AgaveUtils(jwt=user.jwt)
    tapis.create_file(system_id=project.system_id,
                      system_path=project.system_path,
                      file_name=file_name,
                      file_content=file_content)

    # TODO catch any exceptions and log user/project-id and what optional steps failed


def on_project_deletion():
    pass
