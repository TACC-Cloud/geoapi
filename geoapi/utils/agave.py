import shutil
from tempfile import NamedTemporaryFile
from dataclasses import dataclass

import requests
import pathlib
from typing import List, Dict, IO
from urllib.parse import quote, urlparse, parse_qs
import json
from geoapi.log import logging
from dateutil import parser

from geoapi.settings import settings
from geoapi.utils.tenants import get_api_server, get_service_accounts
from geoapi.exceptions import MissingServiceAccount
from geoapi.custom import custom_system_user_retrieval

logger = logging.getLogger(__name__)


class AgaveFileGetError(Exception):
    '''' Unable to fetch file from agave
    '''
    pass


class AgaveFileListing:

    def __init__(self, data: Dict):
        self._links = data["_links"]
        self.system = data["system"]
        self.type = data["type"]
        self.length = data["length"]
        self.path = pathlib.Path(data["path"])
        self.mimeType = data["mimeType"]
        self.lastModified = parser.parse(data["lastModified"])

    def __repr__(self):
        return "<AgaveFileListing {}>".format(self.path)

    @property
    def ext(self):
        return self.path.suffix.lstrip('.').lower()

    @property
    def uuid(self):
        """
        In the files `_links` is an href to metadata via associationIds. The
        `associationId` is the UUID of this file. Use urlparse to parse the URL and then
        the query. The `q` query parameter is a JSON string in the form::

            {"assocationIds": "{{ uuid }}"}

        :return: string: the UUID for the file
        """
        if 'metadata' in self._links:
            assoc_meta_href = self._links['metadata']['href']
            parsed_href = urlparse(assoc_meta_href)
            query_dict = parse_qs(parsed_href.query)
            if 'q' in query_dict:
                meta_q = json.loads(query_dict['q'][0])
                return meta_q.get('associationIds')
        return None


class AgaveUtils:
    BASE_URL = 'http://api.prod.tacc.cloud'

    def __init__(self, jwt=None, token=None, tenant=None):
        client = requests.Session()
        if jwt:
            client.headers.update({'X-JWT-Assertion-designsafe': jwt})
        if token:
            client.headers.update({'Authorization': 'Bearer {}'.format(token)})
        # Use tenant's api server (if tenant is provided) to allow for use
        # of service account which are specific to a tenant
        self.base_url = get_api_server(tenant) if tenant else self.BASE_URL
        self.client = client

    def get(self, url):
        return self.client.get(self.base_url + url)

    def systemsList(self):
        resp = self.get(quote('/systems/'))
        listing = resp.json()
        return listing["result"]

    def systemsGet(self, systemId: str) -> Dict:
        url = quote('/systems/{}'.format(systemId))
        resp = self.get(url)
        listing = resp.json()
        return listing["result"]

    def systemsRolesGet(self, systemId: str) -> Dict:
        url = quote('/systems/{}/roles'.format(systemId))
        resp = self.get(url)
        listing = resp.json()
        return listing["result"]

    def listing(self, systemId: str, path: str) -> List[AgaveFileListing]:
        url = quote('/files/listings/system/{}/{}?limit=10000'.format(systemId, path))
        resp = self.get(url)
        listing = resp.json()
        out = [AgaveFileListing(d) for d in listing["result"]]
        return out

    def getMetaAssociated(self, uuid: str) -> Dict:
        """
        Get metadata associated with a file object for Rapid
        :param uuid: str
        :return: Dict
        """
        q = {'associationIds': uuid}
        qstring = quote(json.dumps(q), safe='')
        url = '/meta/data?q={}'.format(qstring)
        resp = self.get(url)
        meta = resp.json()
        results = [rec["value"] for rec in meta["result"]]
        out = {k: v for d in results for k, v in d.items()}
        return out

    def getFile(self, systemId: str, path: str) -> IO:
        """
        Download a file from agave
        :param systemId: str
        :param path: str
        :return: temporary file
        """
        url = quote('/files/media/system/{}/{}'.format(systemId, path))
        try:
            with self.client.get(self.base_url + url, stream=True) as r:
                if r.status_code == 403:
                    # This is a workaround for bug documented in https://jira.tacc.utexas.edu/browse/CS-169
                    # and in https://jira.tacc.utexas.edu/browse/DES-2084 where sometimes a 403 is returned by tapis
                    # for some files.
                    logger.warn("Could not fetch file ({}/{}) due to unexpected 403. "
                                "Possibly CS-169/DES-2084.".format(systemId, path))
                    systemInfo = self.systemsGet(systemId)
                    if systemInfo["public"]:
                        logger.warn("As system is a public storage system for projects. we will use service "
                                    "account to get file: {}/{}".format(systemId, path))
                        return self._get_file_using_service_account(systemId, path)
                    else:
                        logger.warn("{}/{}.  System is not public so not trying "
                                    "work-around for CS-169/DES-2084.".format(systemId, path))
                if r.status_code > 400:
                    raise AgaveFileGetError("Could not fetch file ({}/{}) status_code:{}".format(systemId,
                                                                                                 path,
                                                                                                 r.status_code))
                tmpFile = NamedTemporaryFile()
                for chunk in r.iter_content(1024 * 1024):
                    tmpFile.write(chunk)
                tmpFile.seek(0)
                return tmpFile
        except Exception as e:
            logger.error("Could not fetch file ({}/{}): {}".format(systemId, path, e))
            raise e

    def _get_file_using_service_account(self, systemId: str, path: str) -> IO:
        """
        Download a file from agave using service account

        :param systemId: str
        :param path: str
        :return: temporary file
        """
        service_client = service_account_client("designsafe")
        url = quote('/files/media/system/{}/{}'.format(systemId, path))
        with service_client.client.get(service_client.base_url + url, stream=True) as r:
            if r.status_code > 400:
                raise AgaveFileGetError("Could not fetch file ({}/{}) with "
                                        "service account status_code:{}".format(systemId,
                                                                                path,
                                                                                r.status_code))
            tmpFile = NamedTemporaryFile()
            for chunk in r.iter_content(1024 * 1024):
                tmpFile.write(chunk)
            tmpFile.seek(0)
            return tmpFile

    def getRawFileToPath(self, systemId: str, fromPath: str, toPath: str):
        url = quote('/files/media/system/{}/{}'.format(systemId, fromPath))
        try:
            with self.client.get(self.base_url + url, stream=True) as r:
                if r.status_code > 400:
                    raise ValueError("Could not fetch file: {}".format(r.status_code))
                with open(toPath, 'wb') as out_file:
                    r.raw.decode_content = True
                    shutil.copyfileobj(r.raw, out_file)
        except Exception as e:
            logger.error(e)
            raise e


def service_account_client(tenant_id):
    try:
        tenant_secrets = json.loads(settings.TENANT)
    except TypeError:
        logger.error("Could not get service account for tenant:{};  Ensure this your environment "
                     "is properly configured.".format(tenant_id))
        raise MissingServiceAccount

    if tenant_secrets is None or tenant_id.upper() not in tenant_secrets:
        raise MissingServiceAccount

    client = AgaveUtils(token=tenant_secrets[tenant_id.upper()]['service_account_token'], tenant=tenant_id)
    return client


@dataclass(frozen=True, eq=True)
class SystemUser:
    username: str
    admin: bool = False


def get_default_system_users(tenant_id, jwt, system_id: str) -> List[SystemUser]:
    """
    Get systems users for a system using a user's jwt and (potentially) the tenant's service account.

    Tapis provides all roles for owner of system which is why we attempt
    to use the service account super token as well.

    :param tenant_id: tenant id
    :param jwt: jwt of a user
    :param system_id: str
    :return: list of users with admin status
    """

    client = AgaveUtils(jwt)
    user_names = [entry["username"] for entry in client.systemsRolesGet(system_id)]

    try:
        client = service_account_client(tenant_id)
        user_names_from_service_account = [entry["username"] for entry in client.systemsRolesGet(system_id)]
        user_names = set(user_names + user_names_from_service_account)
    except MissingServiceAccount:
        logger.error("No service account. Unable to get system roles/users for {}".format(system_id))
    except: # noqa
        logger.exception("Unable to get system roles/users for {} using service account".format(system_id))

    # remove any possible service accounts
    for u in get_service_accounts(tenant_id):
        try:
            user_names.remove(u)
        except (ValueError, KeyError):
            pass  # do nothing if no service account

    logger.info("System:{} has the following users: {}".format(system_id, user_names))
    return [SystemUser(username=u, admin=False) for u in user_names]


def get_system_users(tenant_id, jwt, system_id: str) -> List[SystemUser]:
    """
    Get systems users for a system and their admin status.

    Right now, this would always be DesignSafe.

    :param tenant_id: tenant id
    :param jwt: jwt of a user
    :param system_id: str
    :return: list of users with admin status
    """

    if tenant_id in custom_system_user_retrieval:
        return custom_system_user_retrieval[tenant_id](tenant_id, jwt, system_id)

    return get_default_system_users(tenant_id, jwt, system_id)


def get_metadata_using_service_account(tenant_id: str, system_id: str, path: str) -> Dict:
    """
    Get a file's geolocation metadata using service account

    :param tenant_id: tenant id
    :param system_id: str
    :param path: str
    :return: dict
    """
    logger.debug("tenant:{}, system_id: {} , path:{}".format(tenant_id, system_id, path))
    client = service_account_client(tenant_id)
    uuid = client.listing(system_id, path)[0].uuid
    meta = client.getMetaAssociated(uuid)
    return meta
