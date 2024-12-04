import shutil
import re
import os
import io
import time
from tempfile import NamedTemporaryFile
from dataclasses import dataclass
from functools import wraps
from contextlib import closing
import requests
import pathlib
from typing import List, Dict, IO
from urllib.parse import quote
import json
from dateutil import parser

from geoapi.log import logging
from geoapi.settings import settings
from geoapi.utils.tenants import get_tapis_api_server
from geoapi.custom import custom_system_user_retrieval
from geoapi.models import User
from geoapi.services.users import UserService, ExpiredTokenError, RefreshTokenError
from geoapi.utils import jwt_utils

logger = logging.getLogger(__name__)

SLEEP_SECONDS_BETWEEN_RETRY = 2


class AgaveListingError(Exception):
    """Exception raised when unable to list directory from Agave.
    Attributes:
        response -- response object that caused the error
        message -- explanation of the error
    """

    def __init__(self, response, message):
        self.response = response
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message} | Response: {self.response}"


class AgaveFileGetError(Exception):
    """' Unable to fetch file from agave"""

    pass


class RetryableTapisFileError(Exception):
    """Tapis file errors which are known to possibly work if retried.

    This is raised if we know it is an error that we can re-attempt to get. Note that if we
    try multiple times, and it still doesn't work, we then raise a AgaveFileGetError exception
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
        return self.path.suffix.lstrip(".").lower()


def get_session(user: User):
    """
    Get the client session which contains correct headers

    :param user: The user object containing the JWT.
    """
    client = requests.Session()
    client.headers.update({"X-Tapis-Token": user.jwt})
    return client


class EnsureValidTokenMeta(type):
    def __new__(cls, name, bases, dct):
        for attr_name, attr in dct.items():
            if callable(attr) and not attr_name.startswith("_"):
                dct[attr_name] = cls.wrap_method(attr)
        return super().__new__(cls, name, bases, dct)

    @staticmethod
    def wrap_method(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            self._ensure_valid_token()
            return method(self, *args, **kwargs)

        return wrapper


class ApiUtils(metaclass=EnsureValidTokenMeta):
    """
    Class that handle's the client session for a user using an API that uses Tapis tokens for auth.

    The metaclass EnsureValidTokenMeta is used to ensure that we are calling _ensure_valid_token() before
    making any calls to ensure that any request has a valid token.

    :param database_session: database session
    :param user: The user object containing the JWT.
    :param base_url: The base URL for the API endpoints.
    """

    def __init__(self, database_session, user: User, base_url: str):
        self.database_session = database_session
        self.user = user
        self.base_url = base_url
        self.client = get_session(user)

    def get(self, url, params=None):
        """Make get request"""
        return self.client.get(self.base_url + url, params=params)

    def _ensure_valid_token(self):
        """
        Ensures there is a valid token.

        Method checks if we need to refresh token

        Raises:
            ExpiredTokenError: If unable to ensure there is a valid token
        """
        try:
            # if we can refresh token, and our token is about to expire,
            # let's go ahead and refreshit.
            if (
                self.user.has_unexpired_refresh_token()
                and self.user.auth.access_token
                and jwt_utils.token_will_expire_soon(self.user.auth.access_token)
            ):
                logger.debug(
                    f"user:{self.user} has a token about to expire or has expired; we will refresh it."
                )

                UserService.refresh_access_token(self.database_session, self.user)

                # Update the user and then the client after refreshing the token
                self.user = (
                    self.database_session.query(User)
                    .filter(User.id == self.user.id)
                    .one()
                )
                self.client = get_session(self.user)
        except RefreshTokenError:
            logger.error(
                f"There was a problem refreshing access token of user:{self.user.username}."
            )
        except Exception:
            logger.exception(
                f"Something went wrong when ensuring that token was valid for user:{self.user.username}"
            )

        if not self.user.has_valid_token():
            msg = f"Access token of user:{self.user.username} is expired (or invalid)."
            logger.error(msg)
            raise ExpiredTokenError(msg)


# TODO_TAPISV3 rename AgaveUtils to TapisUtils:  rename agave.py to external_api(?)
class AgaveUtils(ApiUtils):
    def __init__(self, database_session, user: User):
        """
        Initializes the client session for a user.

        This constructor sets up a client session with headers updated for user's JWT.
        """
        super().__init__(
            database_session=database_session,
            user=user,
            base_url=get_tapis_api_server(user.tenant_id),
        )

    def systemsGet(self, systemId: str) -> Dict:
        url = quote("/v3/systems/{}".format(systemId))
        resp = self.get(url)
        listing = resp.json()
        return listing["result"]

    def systemsRolesGet(self, systemId: str) -> Dict:
        url = quote("/systems/{}/roles".format(systemId))
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
                    response=resp,
                )
                raise e

            listing = resp.json()
            fetched_listings = [AgaveFileListing(d) for d in listing["result"]]
            listings.extend(fetched_listings)
            total_fetched += len(fetched_listings)

            if len(fetched_listings) < limit:
                break
            offset += limit
        return listings

    # TODO_V3_REMOVE
    def getMetaAssociated(self, uuid: str) -> Dict:
        """
        Get metadata associated with a file object for Rapid
        :param uuid: str
        :return: Dict
        """
        q = {"associationIds": uuid}
        qstring = quote(json.dumps(q), safe="")
        url = "/meta/data?q={}".format(qstring)
        resp = self.get(url)
        meta = resp.json()
        results = [rec["value"] for rec in meta["result"]]
        out = {k: v for d in results for k, v in d.items()}
        return out

    def _get_file(self, systemId: str, path: str) -> NamedTemporaryFile:
        """
        Get file

        :raises
            RetryableTapisFileError: If tapis error occurs where its possible to retry
            AgaveFileGetError: Raised if tapis error occurs and uncertain if we can retry

        :param systemId:
        :param path:
        :return:
        """
        url = quote(f"/v3/files/content/{systemId}/{path}")

        # TODO_TAPISV3 what error code do we get if tapis is unable to get our file, but we should try again (500?)
        with self.client.get(self.base_url + url, stream=True) as r:

            if r.status_code > 400:
                if r.status_code != 404:
                    logger.warning(
                        f"Fetch file ({systemId}/{path}) but got {r.status_code}, {r}: {r.content}"
                    )
                    raise RetryableTapisFileError

                raise AgaveFileGetError(
                    "Could not fetch file ({}/{}) status_code:{} content:{}".format(
                        systemId, path, r.status_code, r.content
                    )
                )
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
                logger.error(
                    f"File fetching failed but is retryable: ({systemId}/{path}) "
                )
                if allowed_attempts > 0:
                    time.sleep(SLEEP_SECONDS_BETWEEN_RETRY)
                continue
            except Exception as e:
                logger.exception(
                    f"Could not fetch file and did not attempt to retry: ({systemId}/{path})"
                )
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
            with open(destination_path, "wb+") as target_file:
                shutil.copyfileobj(file_obj, target_file)

    def create_file(
        self, system_id: str, system_path: str, file_name: str, file_content: str
    ):
        """
        Create a file on a Tapis storage system.
        """
        file_content = file_content.encode("utf-8")
        file_like_object = io.BytesIO(file_content)

        files = {"file": (file_name, file_like_object, "plain/text")}
        file_import_url = self.base_url + quote(
            f"/v3/files/ops/{system_id}/{system_path}/{file_name}"
        )
        file_import_url = re.sub(r"(?<!:)/+", "/", file_import_url)
        response = self.client.post(file_import_url, files=files)
        response.raise_for_status()

    def delete_file(self, system_id: str, file_path: str):
        """
        Deletes a file on a Tapis storage system.
        """
        file_delete_url = self.base_url + quote(
            f"/v3/files/ops/{system_id}/{file_path}"
        )
        file_delete_url = re.sub(r"(?<!:)/+", "/", file_delete_url)
        response = self.client.delete(file_delete_url)
        response.raise_for_status()


@dataclass(frozen=True, eq=True)
class SystemUser:
    username: str
    admin: bool = False


def get_system_users(database_session, user: User, system_id: str) -> List[SystemUser]:
    """
    Get systems users for a system and their admin status.

    Right now, this would always be DesignSafe.

    :param database_session: Database session
    :param user: User to make the query
    :param system_id: str
    :return: list of users with admin status
    """
    return custom_system_user_retrieval[user.tenant_id.upper()](
        database_session, user, system_id
    )


def get_metadata(database_session, user: User, system_id: str, path: str) -> Dict:
    """
    Get a file's tapis metadata (which typically include geolocation) using service account

    :param database_session: Database session
    :param user: User to make the query
    :param system_id: system id
    :param path: path to file
    :return: dictionary containing the metadata (including geolocation) of a file
    """

    logger.debug(f"getting metadata. system_id: {system_id}, path:{path}")

    client = ApiUtils(
        database_session=database_session, user=user, base_url=settings.DESIGNSAFE_URL
    )
    response = client.get(url=quote(f"/api/filemeta/{system_id}/{path}"))
    response.raise_for_status()
    meta_response = response.json()
    meta = meta_response["value"] if "value" in meta_response else {}
    logger.debug(f"got metadata. system_id: {system_id}, path:{path} -> {meta}")
    return meta
