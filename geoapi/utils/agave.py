import shutil
import re
import os
import io
import time
from tempfile import NamedTemporaryFile
from dataclasses import dataclass

import requests
import pathlib
from typing import List, Dict, IO
from urllib.parse import quote
import json
from geoapi.log import logging
from dateutil import parser

from geoapi.settings import settings
from geoapi.utils.tenants import get_api_server
from geoapi.exceptions import MissingServiceAccount
from geoapi.custom import custom_system_user_retrieval
from geoapi.models import User
from contextlib import closing

logger = logging.getLogger(__name__)

SLEEP_SECONDS_BETWEEN_RETRY = 2


class AgaveListingError(Exception):
    ''' Exception raised when unable to list directory from Agave.
    Attributes:
        response -- response object that caused the error
        message -- explanation of the error
    '''

    def __init__(self, response, message):
        self.response = response
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message} | Response: {self.response}"


class AgaveFileGetError(Exception):
    '''' Unable to fetch file from agave
    '''
    pass


class RetryableTapisFileError(Exception):
    """ Tapis file errors which are known to possibly work if retried.

        This is raised if we know its an error that we can re-attempt to get. Note that if we
        try multiple times and it still doesn't work, we then raise a AgaveFileGetError exception
    """
    pass


class AgaveFileListing:

    def __init__(self, data: Dict):
        self.type = data["type"]
        self.path = pathlib.Path(data["path"])
        self.lastModified = parser.parse(data["lastModified"])

    def __repr__(self):
        return "<AgaveFileListing {}>".format(self.path)

    @property
    def ext(self):
        return self.path.suffix.lstrip('.').lower()


# TODO_TAPISV# rename AgaveUtils to TapisUtils
class AgaveUtils:
    def __init__(self, user):
        """
        Initializes the client session for a user.

        This constructor sets up a client session with headers updated for user's JWT.
        """
        client = requests.Session()

        client.headers.update({'X-Tapis-Token': user.jwt})

        self.tenant_id = user.tenant_id
        self.base_url = get_api_server(user.tenant_id)
        self.client = client

    def get(self, url, params=None):
        return self.client.get(self.base_url + url, params=params)

    def systemsGet(self, systemId: str) -> Dict:
        url = quote('/v3/systems/{}'.format(systemId))
        resp = self.get(url)
        listing = resp.json()
        return listing["result"]

    def systemsRolesGet(self, systemId: str) -> Dict:
        url = quote('/systems/{}/roles'.format(systemId))
        resp = self.get(url)
        listing = resp.json()
        return listing["result"]

    def listing(self, systemId: str, path: str) -> List[AgaveFileListing]:
        listings = []
        offset = 0
        limit = 1000  # Set the limit for each request
        total_fetched = 0

        while True:
            url = quote(f"/v3/files/ops/{systemId}/{path}")
            resp = self.get(url, params={"offset": offset, "limit": limit})
            if resp.status_code != 200:
                e = AgaveListingError(
                    message=f"Unable to perform files listing of {systemId}/{path}. Status code: {resp.status_code}",
                    response=resp)
                raise e

            listing = resp.json()
            fetched_listings = [AgaveFileListing(d) for d in listing["result"]]
            listings.extend(fetched_listings)
            total_fetched += len(fetched_listings)

            if len(fetched_listings) < limit:
                break
            offset += limit
        return listings

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

    def _get_file(self, systemId: str, path: str, use_service_account: bool = False) -> NamedTemporaryFile:
        """
        Get file

        :raises
            RetryableTapisFileError: If tapis error occurs where its possible to retry
            AgaveFileGetError: Raised if tapis error occurs and uncertain if we can retry

        :param systemId:
        :param path:
        :parm use_service_account: if service account should be used
        :return:
        """
        url = quote(f"/v3/files/content/{systemId}/{path}")

        client = service_account_client(self.tenant_id).client if use_service_account else self.client

        # TODO_TAPISV3 what error code do we get if tapis is unable to get our file, but we should try again (500?)
        with client.get(self.base_url + url, stream=True) as r:

            if r.status_code > 400:
                if r.status_code != 404:
                    logger.warning(f"Fetch file ({systemId}/{path}) but got {r.status_code}, {r}: {r.content}")
                    raise RetryableTapisFileError

                raise AgaveFileGetError("Could not fetch file ({}/{}) status_code:{} content:{}".format(systemId,
                                                                                                        path,
                                                                                                        r.status_code,
                                                                                                        r.content))
            tmpFile = NamedTemporaryFile()
            for chunk in r.iter_content(1024 * 1024):
                tmpFile.write(chunk)
            tmpFile.seek(0)

            # TODO_TAPISV3 is this still needed; this was a v2 error where empty files were sometimes returned
            if os.path.getsize(tmpFile.name) < 1:
                logger.warning(f"Fetch file ({systemId}/{path}) but is empty. ")
                raise RetryableTapisFileError
        return tmpFile

    def getFile(self, systemId: str, path: str) -> NamedTemporaryFile:
        """
        Download a file from tapis

        We attempt to get the file multiple times in case tapis is having issues (like if we see CS-196/DES-2236
        where tapis hits an ssh limits and then we get a a 500 or a file with 0 bytes). Eventually
        we will raise AgaveFileGetError if we can't get the file.

        User needs to ensure they call `close()` on the returned temp file

        :raises
            AgaveFileGetError: Raised if unable to get file via tapis.

        :param systemId: str
        :param path: str
        :return: temporary file
        """
        allowed_attempts = 5
        while allowed_attempts > 0:
            try:
                logger.debug(f"Getting file {systemId}/{path}")
                return self._get_file(systemId, path)
            except RetryableTapisFileError:
                allowed_attempts = allowed_attempts - 1
                logger.error(f"File fetching failed but is retryable: ({systemId}/{path}) ")
                if allowed_attempts > 0:
                    time.sleep(SLEEP_SECONDS_BETWEEN_RETRY)
                continue
            except Exception as e:
                logger.exception(f"Could not fetch file and did not attempt to retry: ({systemId}/{path})")
                raise e
        msg = f"Could not fetch file and no longer retrying.: ({systemId}/{path})"
        logger.exception(msg)
        raise AgaveFileGetError(msg)

    def get_file_context_manager(self, system_id: str, path: str) -> IO:
        tmpFile = self.getFile(system_id, path)
        return closing(tmpFile)

    def get_file_to_path(self, system_id: str, path: str, destination_path: str):
        """
          Download a file from tapis

          This method differs from getFile as here we write to non-temporary file

          :param system_id: str
          :param path: str
          :param destination_path: str desired location of file

          :return: temporary file
        """
        with self.get_file_context_manager(system_id, path) as file_obj:
            with open(destination_path, 'wb+') as target_file:
                shutil.copyfileobj(file_obj, target_file)

    def create_file(self, system_id: str, system_path: str, file_name: str, file_content: str):
        """
        Create a file on a Tapis storage system.
        """
        file_content = file_content.encode('utf-8')
        file_like_object = io.BytesIO(file_content)

        files = {
            'file': (file_name, file_like_object, 'plain/text')
        }
        file_import_url = self.base_url + quote(f"/v3/files/ops/{system_id}/{system_path}/{file_name}")
        file_import_url = re.sub(r'(?<!:)/+', '/', file_import_url)
        response = self.client.post(file_import_url, files=files)
        response.raise_for_status()

    def delete_file(self, system_id: str, file_path: str):
        """
        Deletes a file on a Tapis storage system.
        """
        file_delete_url = self.base_url + quote(f"/v3/files/ops/{system_id}/{file_path}")
        file_delete_url = re.sub(r'(?<!:)/+', '/', file_delete_url)
        response = self.client.delete(file_delete_url)
        response.raise_for_status()


def service_account_client(tenant_id):
    try:
        tenant_secrets = json.loads(settings.TENANT)
    except TypeError:
        logger.exception("Could not get service account for tenant:{};  Ensure this your environment "
                         "is properly configured.".format(tenant_id))
        raise MissingServiceAccount

    if tenant_secrets is None or tenant_id.upper() not in tenant_secrets:
        raise MissingServiceAccount

    client = AgaveUtils(token=tenant_secrets[tenant_id.upper()]['tg458981_service_account_token'], tenant_id=tenant_id)
    token = tenant_secrets[tenant_id.upper()]['tg458981_service_account_token']
    return client


@dataclass(frozen=True, eq=True)
class SystemUser:
    username: str
    admin: bool = False


def get_system_users(user: User, system_id: str) -> List[SystemUser]:
    """
    Get systems users for a system and their admin status.

    Right now, this would always be DesignSafe.

    :param user: User to make the query
    :param system_id: str
    :return: list of users with admin status
    """
    return custom_system_user_retrieval[user.tenant_id.upper()](user, system_id)


def get_metadata_using_service_account(tenant_id: str, system_id: str, path: str) -> Dict:
    """
    Get a file's tapis metadata (which typically include geolocation) using service account

    :param tenant_id: tenant id
    :param system_id: system id
    :param path: path to file
    :return: dictionary containing the metadata (including geolocation) of a file
    """
    logger.debug("getting metadata. tenant:{}, system_id: {} , path:{}".format(tenant_id, system_id, path))

    # TODO_TAPISV3 See https://tacc-main.atlassian.net/browse/WG-254
    return {}

    client = service_account_client(tenant_id)
    meta_data_query = {
            "name": "designsafe.file",
            "value.system": system_id,
            "value.path": os.path.join(path, '*')
    }
    params = {"limit": 300, "offset": 0, "q": json.dumps(meta_data_query)}

    # same as Tapis v2 python client's: client.meta.listMetadata(q=json.dumps(query), limit=300, offset=0)
    response = client.get(url=quote('/meta/v2/data/'), params=params)
    response.raise_for_status()
    meta_list = response.json()["result"]
    if len(meta_list) > 0 and "value" in meta_list[0]:
        return meta_list[0]["value"]
    return {}
