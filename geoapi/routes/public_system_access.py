from datetime import datetime
from pydantic import BaseModel, ConfigDict
from litestar import Controller, get, post, Request
from celery import uuid as celery_uuid
from sqlalchemy.orm import Session

from geoapi.log import logger
from geoapi.models import Feature, FeatureAsset
from geoapi.routes.projects import FeatureAssetModel, TaskModel
from geoapi.utils.decorators import project_permissions_guard
from geoapi.tasks.public_system_access_check import check_and_update_system_paths


class PublicStatusModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    started_at: datetime
    completed_at: datetime | None = None
    task: TaskModel | None = None


class StartPublicStatusRefreshResponse(BaseModel):
    message: str
    public_status_id: int
    task_id: int | None = None


class ProjectPublicStatusSummary(BaseModel):
    project_id: int
    check: PublicStatusModel | None = None
    files: list[FeatureAssetModel]


class ProjectPublicStatusController(Controller):
    # Mounted under projects_router which provides /projects prefix
    path = "/{project_id:int}/public-system-access"

    @post(
        "/",
        tags=["projects"],
        operation_id="start_public_system_access_status_refresh",
        description="Start checking public system access status for project files",
        guards=[project_permissions_guard],
        status_code=202,
    )
    def start_public_status_refresh(
        self, request: Request, db_session: Session, project_id: int
    ) -> StartPublicStatusRefreshResponse:
        """
        Start a background task to refresh public-system-access status of files.

        This checks all feature assets in the project and updates their
        current_system/current_path if they're found in the published location.
        """
        from geoapi.services.public_system_access import PublicSystemAccessService

        user = request.user
        logger.info(
            f"Starting public status refresh for project:{project_id} by user:{user.username}"
        )

        # Check if there's already a running refresh
        if PublicSystemAccessService.has_running_check(db_session, project_id):
            existing = PublicSystemAccessService.get(db_session, project_id)
            return StartPublicStatusRefreshResponse(
                message="A public status refresh is already in progress for this project",
                public_status_id=existing.id,
                task_id=existing.task_id,
            )

        # Generate Celery task UUID
        celery_task_uuid = celery_uuid()

        # Create the check record and Task in database
        public_access_check = PublicSystemAccessService.start_check(
            db_session, project_id, celery_task_uuid=celery_task_uuid
        )

        # Start Celery task with the UUID we generated
        check_and_update_system_paths.apply_async(
            args=[user.id, project_id, public_access_check.id],
            task_id=celery_task_uuid,
        )

        return StartPublicStatusRefreshResponse(
            message="Public status refresh started",
            public_status_id=public_access_check.id,
            task_id=public_access_check.task_id,  # Return the database task.id
        )

    @get(
        "/files",
        tags=["projects"],
        operation_id="get_public_files_status",
        description="Get public/private status of all files in the project with last refresh info",
        guards=[project_permissions_guard],
    )
    def get_files_status(
        self, request: Request, db_session: "Session", project_id: int
    ) -> ProjectPublicStatusSummary:
        """
        Get detailed status of which files are public vs private.

        Single endpoint that returns both file-level details and last refresh info.
        """
        from geoapi.services.public_system_access import PublicSystemAccessService

        logger.info(
            f"Getting public files status for project:{project_id} "
            f"by user:{request.user.username}"
        )

        # Get all feature assets
        # NOTE: Only includes Features with FeatureAssets. Features without assets
        #       (geometry-only, like manually drawn shapes) are excluded from this list.
        # TODO WG-600: Handle "source file" FeatureAssets (shapefiles, geojson) that represent
        #              the file that created the feature. These show up in results if they
        #              have original_system/path set, but may need different UI treatment.
        feature_assets = (
            db_session.query(FeatureAsset)
            .join(Feature, Feature.id == FeatureAsset.feature_id)
            .filter(Feature.project_id == project_id)
            .all()
        )

        # TODO with WG-600 or before then we should include a list of features that aren't accounted for here just so
        # users are aware of a gap of knowledge

        # Get most recent check
        public_access_check = PublicSystemAccessService.get(db_session, project_id)

        files_status = [
            FeatureAssetModel.model_validate(asset) for asset in feature_assets
        ]

        return ProjectPublicStatusSummary(
            project_id=project_id,
            check=(
                PublicStatusModel.model_validate(public_access_check)
                if public_access_check
                else None
            ),
            files=files_status,
        )
