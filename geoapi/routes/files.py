from litestar import Controller, Request, post
from sqlalchemy.orm import Session

from geoapi.log import logger
from geoapi.schema.files import (
    FileInspectRequest,
    FileInspectResponse,
    FileListEntry,
    FileListRequest,
)
from geoapi.services.file_inspection import FileInspectionService
from geoapi.utils.decorators import not_anonymous_guard


class FileInspectController(Controller):
    path = "/files"

    @post(
        "/inspect",
        status_code=200,
        tags=["files"],
        operation_id="inspect_file",
        description=(
            "Inspect a Tapis path (a file or a directory, recursively) with "
            "GDAL/OGR/PDAL and return a deterministic geospatial verdict per file. "
            "Always returns a list (a file yields a list of one)."
        ),
        guards=[not_anonymous_guard],
    )
    def inspect_file(
        self, request: Request, data: FileInspectRequest
    ) -> list[FileInspectResponse]:
        logger.info(
            f"inspect_file: user:{request.user.username} "
            f"system:{data.system_id} path:{data.path}"
        )
        return FileInspectionService.inspect(
            user_id=request.user.id,
            system_id=data.system_id,
            path=data.path,
            recursive=data.recursive,
        )

    @post(
        "/list",
        status_code=200,
        tags=["files"],
        operation_id="list_files",
        description=(
            "List a Tapis path (a file or a directory, recursively) and return a quick, "
            "extension-only geospatial guess per file. Fast heuristic only (i.e. no fetch and proessing performed). Use "
            "/files/inspect for a real verdict."
        ),
        guards=[not_anonymous_guard],
    )
    def list_files(
        self, request: Request, db_session: Session, data: FileListRequest
    ) -> list[FileListEntry]:
        logger.info(
            f"list_files: user:{request.user.username} "
            f"system:{data.system_id} path:{data.path}"
        )
        return FileInspectionService.list_files(
            session=db_session,
            user_id=request.user.id,
            system_id=data.system_id,
            path=data.path,
            recursive=data.recursive,
        )
