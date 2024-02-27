from geoapi.custom.designsafe.project_users import get_system_users
from geoapi.custom.designsafe.project import on_project_creation, on_project_deletion

custom_system_user_retrieval = {"DESIGNSAFE": get_system_users}

custom_on_project_creation = {"DESIGNSAFE": on_project_creation,
                              "PORTALS": on_project_creation}  # TODO_TAPISV3 using portals for testing

custom_on_project_deletion = {"DESIGNSAFE": on_project_deletion,
                              "PORTALS": on_project_deletion}  # TODO_TAPISV3 using portals for testing
