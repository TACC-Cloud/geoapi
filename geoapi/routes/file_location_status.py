from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict
from litestar import Controller, get, post, Request
from celery import uuid as celery_uuid
from sqlalchemy.orm import Session

from geoapi.log import logger
from geoapi.models import Feature, FeatureAsset
from geoapi.schema.projects import FeatureAssetModel, TaskModel
from geoapi.utils.decorators import project_permissions_guard
from geoapi.tasks.file_location_check import check_and_update_file_locations


class FileLocationStatusModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    started_at: datetime
    completed_at: datetime | None = None
    task: TaskModel | None = None
    total_files: int | None = None
    files_checked: int | None = None
    files_failed: int | None = None


class StartFileLocationStatusRefreshResponse(BaseModel):
    message: str
    public_status_id: int
    task_id: int | None = None


class ProjectFileLocationStatusSummary(BaseModel):
    project_id: int
    check: FileLocationStatusModel | None = None
    files: list[FeatureAssetModel]


class ProjectFileLocationStatusController(Controller):
    # Mounted under projects_router which provides /projects prefix
    path = "/{project_id:int}/file-location-status"

    @post(
        "/",
        tags=["projects"],
        operation_id="start_file_location_refresh",
        description="Start checking and updating file location (and public access) for project files",
        guards=[project_permissions_guard],
        status_code=202,
    )
    def start_public_status_refresh(
        self, request: Request, db_session: Session, project_id: int
    ) -> StartFileLocationStatusRefreshResponse:
        """
        Start a background task to refresh public-system-access status of files.

        This checks all feature assets in the project and updates their
        current_system/current_path if they're found in the published location.
        """
        from geoapi.services.file_location_status import FileLocationStatusService
        from geoapi.models import TaskStatus

        user = request.user
        logger.info(
            f"Starting public status refresh for project:{project_id} by user:{user.username}"
        )

        # Check if there's already a running refresh
        if FileLocationStatusService.has_running_check(db_session, project_id):
            existing = FileLocationStatusService.get(db_session, project_id)
            return StartFileLocationStatusRefreshResponse(
                message="A public status refresh is already in progress for this project",
                public_status_id=existing.id,
                task_id=existing.task_id,
            )

        # Generate Celery task UUID
        celery_task_uuid = str(celery_uuid())

        # Create the check record and Task in database
        file_location_check = FileLocationStatusService.start_check(
            db_session, project_id, celery_task_uuid=celery_task_uuid
        )

        # Try to start Celery task
        try:
            check_and_update_file_locations.apply_async(
                args=[user.id, project_id],
                task_id=celery_task_uuid,
            )
        except Exception as e:
            # Mark task as failed if we couldn't queue it
            logger.error(
                f"Failed to queue file location check task for project:{project_id}: {e}"
            )
            if file_location_check.task:
                file_location_check.task.status = TaskStatus.FAILED
                file_location_check.task.latest_message = (
                    f"Failed to queue task: {str(e)}"
                )
            file_location_check.completed_at = datetime.now(timezone.utc)
            db_session.commit()

            raise  # Re-raise to return 500 to client

        return StartFileLocationStatusRefreshResponse(
            message="Public status refresh started",
            public_status_id=file_location_check.id,
            task_id=file_location_check.task_id,
        )

    @get(
        "/files",
        tags=["projects"],
        operation_id="get_public_files_status",
        description="Get public/private status of all files in the project with last refresh info",
        guards=[project_permissions_guard],
    )
    def get_files_status(
        self, request: Request, db_session: Session, project_id: int
    ) -> ProjectFileLocationStatusSummary:
        """
        Get detailed status of which files are public vs private.

        Single endpoint that returns both file-level details and last refresh info.
        """
        from geoapi.services.file_location_status import FileLocationStatusService

        logger.info(
            f"Getting public files status for project:{project_id} "
            f"by user:{request.user.username}"
        )

        # Get all feature assets
        # NOTE: Only includes Features with FeatureAssets. Features without assets
        #       (geometry-only, like manually drawn shapes) are excluded from this list.
        #       See WG-600. Also consider tile layers (internal cogs)
        feature_assets = (
            db_session.query(FeatureAsset)
            .join(Feature, Feature.id == FeatureAsset.feature_id)
            .filter(Feature.project_id == project_id)
            .all()
        )

        # TODO with WG-600 or before then we should include a list of features that aren't accounted for here just so
        # users are aware of a gap of knowledge

        # Get most recent check
        public_access_check = FileLocationStatusService.get(db_session, project_id)

        files_status = [
            FeatureAssetModel.model_validate(asset) for asset in feature_assets
        ]

        # Convert check with nested task validation
        check_data = None
        if public_access_check:
            check_data = FileLocationStatusModel(
                id=public_access_check.id,
                project_id=public_access_check.project_id,
                started_at=public_access_check.started_at,
                completed_at=public_access_check.completed_at,
                task=(
                    TaskModel.model_validate(public_access_check.task)
                    if public_access_check.task
                    else None
                ),
            )

        return ProjectFileLocationStatusSummary(
            project_id=project_id,
            check=check_data,
            files=files_status,
        )
