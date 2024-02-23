from urllib.parse import quote


def get_system_users(tenant_id, jwt, system_id: str):
    """
    Get systems users based on the DesignSafe project's co-pis and pis.

    :param tenant_id: tenant id
    :param jwt: jwt of a user
    :param system_id: str
    :return: list of users with admin status
    """
    from geoapi.utils.agave import service_account_client, SystemUser, get_default_system_users

    # TODO_TAPISV3 https://tacc-main.atlassian.net/browse/WG-257
    if not system_id.startswith("project-"):
        return get_default_system_users(tenant_id, jwt, system_id)

    uuid = system_id[len("project-"):]
    client = service_account_client(tenant_id=tenant_id)
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
