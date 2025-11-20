from geoapi.exceptions import GetUsersForProjectNotSupported
from geoapi.custom.designsafe.utils import get_designsafe_project_data


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

    project = get_designsafe_project_data(
        database_session=database_session, user=user, system_id=system_id
    )

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
