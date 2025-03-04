from geoapi.exceptions import GetUsersForProjectNotSupported
from geoapi.log import logger
from geoapi.settings import settings
from geoapi.models import User


def get_project_data(database_session, user: User, system_id: str) -> dict:
    """
    Get project data for a certain system

    :param database_session: db session
    :param user: user to use when querying system from DesignSafe
    :param system_id: str
    :return: project data

    """
    from geoapi.utils.external_apis import ApiUtils

    logger.debug(f"Getting project metadata for system:{system_id}")

    uuid = system_id[len("project-") :]
    client = ApiUtils(database_session, user, settings.DESIGNSAFE_URL)
    resp = client.get(f"/api/projects/v2/{uuid}/")
    resp.raise_for_status()

    project = resp.json()["baseProject"]["value"]
    return project


def _is_designsafe_project_guest_user(user):
    if "username" not in user or user["role"] == "guest":
        return True
    else:
        return False


def get_system_users(database_session, user, system_id: str):
    """
    Get systems users based on the DesignSafe project's co-pis and pis.

    :param database_session: database session
    :param user: user to use when querying system/map users
    :param system_id: str
    :raises GetUsersForProjectNotSupported if system is not a DesignSafe Project
    :return: A list of SystemUser instances, each with a username and an admin status
    """

    from geoapi.utils.external_apis import SystemUser

    if not system_id.startswith("project-"):
        raise GetUsersForProjectNotSupported(
            f"System:{system_id} is not a project so unable to get users"
        )

    project = get_project_data(database_session, user, system_id)

    users = {}
    for u in project["users"]:
        is_admin = u["role"] in ("pi", "co_pi")
        if not _is_designsafe_project_guest_user(u) and u["username"] not in users:
            users[u["username"]] = SystemUser(username=u["username"], admin=is_admin)
        else:
            # there can be duplicates (seen in v2) so we want to ensure we have the "admin=True" version of a duplicate
            if is_admin:
                users[u["username"]] = SystemUser(
                    username=u["username"], admin=is_admin
                )
    return list(users.values())
