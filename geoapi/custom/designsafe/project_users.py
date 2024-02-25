from urllib.parse import quote
from geoapi.exceptions import GetUsersForProjectNotSupported


def get_system_users(user, system_id: str):
    """
    Get systems users based on the DesignSafe project's co-pis and pis.

    :param user: user to use when quering system/map users
    :param system_id: str
    :raises GetUsersForProjectNotSupported if system is not a DesignSafe Project
    :return: list of users with admin status
    """
    from geoapi.utils.agave import AgaveUtils, SystemUser

    if not system_id.startswith("project-"):
        raise GetUsersForProjectNotSupported(f"System:{system_id} is not a project so unable to get users")

    # TODO_TAPISV3 https://tacc-main.atlassian.net/browse/WG-257
    # TODO_TAPISV3 projects endpoint is /api/projects on designsafe portal
    uuid = system_id[len("project-"):]
    client = AgaveUtils(user)
    resp = client.get(quote(f'/projects/v2/{uuid}/'))
    resp.raise_for_status()
    project = resp.json()["value"]
    users = {}
    if "pi" in project:
        users[project["pi"]] = SystemUser(username=project["pi"], admin=True)
    for u in project["coPis"]:
        # check if we have already added this user before adding it
        if u not in users:
            users[u] = SystemUser(username=u, admin=True)
    for u in project["teamMembers"]:
        # check if we have already added this user before adding it
        if u not in users:
            users[u] = SystemUser(username=u, admin=False)
    return list(users.values())
