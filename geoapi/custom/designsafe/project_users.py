from urllib.parse import quote
from geoapi.log import logging

logger = logging.getLogger(__name__)


def get_system_users(tenant_id, jwt, system_id: str):
    """
    Get systems users based on the DesignSafe project's co-pis and pis.

    :param tenant_id: tenant id
    :param jwt: jwt of a user
    :param system_id: str
    :return: list of users with admin status
    """
    from geoapi.utils.agave import service_account_client, SystemUser, get_default_system_users

    if not system_id.startswith("project-"):
        return get_default_system_users(tenant_id, jwt, system_id)

    uuid = system_id[len("project-"):]
    client = service_account_client(tenant_id=tenant_id)
    resp = client.get(quote(f'/projects/v2/{uuid}/'))
    resp.raise_for_status()
    project = resp.json()["value"]
    users = []
    if "pi" in project:
        users.append(SystemUser(username=project["pi"], admin=True))
    for u in project["coPis"]:
        users.append(SystemUser(username=u, admin=True))
    for u in project["teamMembers"]:
        users.append(SystemUser(username=u, admin=False))
    return users
