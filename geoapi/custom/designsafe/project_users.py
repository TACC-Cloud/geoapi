from geoapi.exceptions import GetUsersForProjectNotSupported


def get_system_users(user, system_id: str):
    """
    Get systems users based on the DesignSafe project's co-pis and pis.

    :param user: user to use when quering system/map users
    :param system_id: str
    :raises GetUsersForProjectNotSupported if system is not a DesignSafe Project
    :return: list of users with admin status
    """

    from geoapi.utils.agave import SystemUser

    if not system_id.startswith("project-"):
        raise GetUsersForProjectNotSupported(f"System:{system_id} is not a project so unable to get users")

    # TODO_TAPISV3 https://tacc-main.atlassian.net/browse/WG-257
    # TODO_TAPISV3 projects endpoint is /api/projects on designsafe portal
    # uuid = system_id[len("project-"):]
    #  client = AgaveUtils(user) # TODO_TAPISV3 for a service account and use DesignSafe endpoint
    # url = designsafe_url + quote(f'/api/projects/{uuid}/')
    # resp = client.get(url)
    # resp.raise_for_status()
    # project = resp.json()["value"]

    import os
    import json
    home = os.path.dirname(__file__)
    with open(os.path.join(home, '../../tests/fixtures/designsafe_api_project_hazmapper_designsafe_v3.json'), 'rb') as f:
        project = json.loads(f.read())

    users = {}
    for u in project["users"]:
        admin = False
        if u["role"] in ["pi", "co_pi"]:
            admin = True
        if u["username"] not in users:
            users[u["username"]] = SystemUser(username=u["username"], admin=admin)
        else:
            # there can be duplicates (seen in v2) so we want to ensure we have the "admin" version of a duplicate
            if users[u["username"]].admin:
                users[u["username"]] = SystemUser(username=u["username"], admin=admin)
    return list(users.values())
