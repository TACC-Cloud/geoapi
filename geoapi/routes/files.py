from litestar import Controller, Request, get, post
from sqlalchemy.orm import Session

from geoapi.log import logger
from geoapi.schema.files import (
    FileInspectJobResponse,
    FileInspectRequest,
    FileListJobResponse,
    FileListRequest,
    JobSubmitResponse,
)
from geoapi.services.file_inspection import FileInspectionService
from geoapi.utils.decorators import not_anonymous_guard


class FileInspectController(Controller):
    path = "/files"

    @post(
        "/inspect",
        status_code=202,
        tags=["files"],
        operation_id="inspect_file",
        description=(
            "Submit an inspection of a Tapis path (a file or a directory, recursively). "
            "Inspection runs async on the worker (GDAL/OGR/PDAL + EXIF). Returns a task "
            "id; poll GET /files/inspect/{task_id} for status and the per-file verdicts."
        ),
        guards=[not_anonymous_guard],
    )
    def inspect_file(
        self, request: Request, db_session: Session, data: FileInspectRequest
    ) -> JobSubmitResponse:
        logger.info(
            f"inspect_file: user:{request.user.username} "
            f"system:{data.system_id} path:{data.path}"
        )
        task = FileInspectionService.submit_inspect(
            session=db_session,
            user_id=request.user.id,
            system_id=data.system_id,
            path=data.path,
            recursive=data.recursive,
        )
        return JobSubmitResponse(task_id=task.id, status=task.status)

    @get(
        "/inspect/{task_id:int}",
        tags=["files"],
        operation_id="get_inspect_job",
        description=(
            "Poll an inspection job: returns its status and, once COMPLETED, the "
            "per-file geospatial verdicts."
        ),
        guards=[not_anonymous_guard],
    )
    def get_inspect_job(
        self, request: Request, db_session: Session, task_id: int
    ) -> FileInspectJobResponse:
        return FileInspectionService.get_inspect_job(
            session=db_session, task_id=task_id, user_id=request.user.id
        )

    @post(
        "/list",
        status_code=202,
        tags=["files"],
        operation_id="list_files",
        description=(
            "Submit a listing of a Tapis path (a file or a directory, recursively) with a "
            "quick, extension-only geospatial guess per file (no fetch, no GDAL). Runs "
            "async; returns a task id -- poll GET /files/list/{task_id} for the entries. "
            "Use /files/inspect for a real verdict."
        ),
        guards=[not_anonymous_guard],
    )
    def list_files(
        self, request: Request, db_session: Session, data: FileListRequest
    ) -> JobSubmitResponse:
        logger.info(
            f"list_files: user:{request.user.username} "
            f"system:{data.system_id} path:{data.path}"
        )
        task = FileInspectionService.submit_list(
            session=db_session,
            user_id=request.user.id,
            system_id=data.system_id,
            path=data.path,
            recursive=data.recursive,
        )
        return JobSubmitResponse(task_id=task.id, status=task.status)

    @get(
        "/list/{task_id:int}",
        tags=["files"],
        operation_id="get_list_job",
        description="Poll a list job: returns its status and, once COMPLETED, the entries.",
        guards=[not_anonymous_guard],
    )
    def get_list_job(
        self, request: Request, db_session: Session, task_id: int
    ) -> FileListJobResponse:
        return FileInspectionService.get_list_job(
            session=db_session, task_id=task_id, user_id=request.user.id
        )
