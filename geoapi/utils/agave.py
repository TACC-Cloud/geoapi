from tempfile import NamedTemporaryFile

import requests
import pathlib
from typing import List, Dict, IO
from urllib.parse import quote, urlparse, unquote, parse_qs, urlencode
import json
from geoapi.log import logging
from dateutil import parser
logger = logging.getLogger(__name__)

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

    def __init__(self, jwt):
        self.jwt = jwt
        client = requests.Session()
        client.headers.update({'X-JWT-Assertion-designsafe': jwt})
        self.client = client

    def systemsList(self):
        url = quote('/systems/')
        resp = self.client.get(self.BASE_URL + url)
        listing = resp.json()
        return listing["result"]

    def systemsGet(self, systemId: str) -> Dict:
        url = quote('/systems/{}'.format(systemId))
        resp = self.client.get(self.BASE_URL + url)
        listing = resp.json()
        return listing["result"]

    def listing(self, systemId: str, path: str) -> List[AgaveFileListing]:
        url = quote('/files/listings/system/{}/{}?limit=10000'.format(systemId, path))
        resp = self.client.get(self.BASE_URL + url)
        listing = resp.json()
        out = [AgaveFileListing(d) for d in listing["result"]]
        return out

    def getMetaAssociated(self, uuid:str)->Dict:
        """
        Get metadata associated with a file object for Rapid
        :param uuid: str
        :return: Dict
        """
        q = {'associationIds': uuid}
        qstring = quote(json.dumps(q), safe='')
        url = '/meta/data?q={}'.format(qstring)
        resp = self.client.get(self.BASE_URL + url)
        meta = resp.json()
        results = [rec["value"] for rec in meta["result"]]
        out = {k: v for d in results for k, v in d.items()}
        return out

    def getFile(self, systemId: str, path: str) -> IO:
        """
        Download a file from agave
        :param systemId: str
        :param path: str
        :return: uuid str
        """
        url = quote('/files/media/system/{}/{}'.format(systemId, path))
        try:
            with self.client.get(self.BASE_URL + url, stream=True) as r:
                if r.status_code > 400:
                    raise ValueError("Could not fetch file: {}".format(r.status_code))
                tmpFile = NamedTemporaryFile()
                for chunk in r.iter_content(1024*1024):
                    tmpFile.write(chunk)
                tmpFile.seek(0)
                return tmpFile
        except Exception as e:
            logger.error(e)
            raise e
