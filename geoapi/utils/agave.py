import requests
from typing import List, Dict
from urllib.parse import quote, urljoin, urlparse
import uuid
import json

class AgaveFileListing:

    def __init__(self, data: Dict):
        self._links = data["_links"]
        self.system = data["system"]
        self.type = data["type"]
        self.length = data["length"]
        self.path = data["path"]
        self.mimeType = data["mimeType"]

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
            print(assoc_meta_href)
            parsed_href = urlparse(assoc_meta_href)
            query_dict = urlparse(parsed_href.query)
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

    def listFiles(self, systemId: str, path: str) -> List[AgaveFileListing]:
        url = quote('/files/listings/system/{}/{}'.format(systemId, path))
        print(self.BASE_URL + url)
        resp = self.client.get(self.BASE_URL + url)
        listing = resp.json()
        out = [AgaveFileListing(d) for d in listing["result"]]
        return out

    def getMetaAssociated(self, uuid:str):
        url = quote('/meta/data/{}'.format(uuid))
        resp = self.client.get(self.BASE_URL + url)
        meta = resp.json()
        return meta

    def getFile(self, systemId: str, path: str) -> str:
        """
        Download a file from agave
        :param systemId: str
        :param path: str
        :return: uuid str
        """
        url = quote('/files/media/system/{}/{}'.format(systemId, path))
        print(self.BASE_URL + url)
        struuid = str(uuid.uuid4())
        with self.client.get(self.BASE_URL + url, stream=True) as r:
            with open('/tmp/{}'.format(struuid), 'wb') as fd:
                for chunk in r.iter_content(1024*1024):
                    fd.write(chunk)
        return struuid