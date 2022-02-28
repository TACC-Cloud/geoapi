from datetime import datetime

from geoapi.db import db_session
from geoapi.models import ImportedFile
from geoapi.log import logging

logger = logging.getLogger(__name__)


class ImportsService():

    @staticmethod
    def getImport(projectId: int, systemId: str, path: str) -> ImportedFile:
        return db_session.query(ImportedFile)\
            .filter(ImportedFile.project_id == projectId) \
            .filter(ImportedFile.system_id == systemId) \
            .filter(ImportedFile.path == path)\
            .first()

    @staticmethod
    def createImportedFile(projectId: int,
                           systemId: str,
                           path: str,
                           lastUpdated: datetime,
                           successful_import: bool) -> ImportedFile:
        targetFile = ImportedFile(
            project_id=projectId,
            system_id=systemId,
            path=path,
            last_updated=lastUpdated,
            successful_import=successful_import
        )
        return targetFile
