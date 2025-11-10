from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict
from litestar import Controller, get, post, Request
from celery import uuid as celery_uuid
from sqlalchemy.orm import Session

from geoapi.log import logger
from geoapi.models import Feature, FeatureAsset, TileServer
from geoapi.schema.projects import FeatureAssetModel, TileServerModel, TaskModel
from geoapi.utils.decorators import project_permissions_guard
from geoapi.tasks.file_location_check import check_and_update_file_locations
from geoapi.services.tile_server import TileService

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


class FileLocationSummary(BaseModel):
    """Summary of what is and isn't being checked"""

    total_features: int
    features_with_assets: int  # Checked
    features_without_assets: int  # Not checked ✗
    total_tile_servers: int
    internal_tile_servers: int  # Checked
    external_tile_servers: int  # Not checked


class ProjectFileLocationStatusSummary(BaseModel):
    """
    Summary of file location status for a project.

    Includes both feature assets (photos, videos, point clouds) and tile servers (COG layers).
    """

    project_id: int
    check: FileLocationStatusModel | None = None
    featureAssets: list[FeatureAssetModel]
    tileServers: list[TileServerModel]
    summary: FileLocationSummary


class ProjectFileLocationStatusController(Controller):
    # Mounted under projects_router which provides /projects prefix
    path = "/{project_id:int}/file-location-status"

    @post(
        "/",
        tags=["projects"],
        operation_id="start_file_location_refresh",
        description="Start checking and updating file location (and public access) for project files and tile servers",
        guards=[project_permissions_guard],
        status_code=202,
    )
    def start_public_status_refresh(
        self, request: Request, db_session: Session, project_id: int
    ) -> StartFileLocationStatusRefreshResponse:
        """
        Start a background task to refresh public-system-access status of files and tile servers.

        This checks all feature assets and internal tile servers in the project and updates their
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
        description="Get public/private status of all files and tile servers in the project with last refresh info",
        guards=[project_permissions_guard],
    )
    def get_files_status(
        self, request: Request, db_session: Session, project_id: int
    ) -> ProjectFileLocationStatusSummary:
        """
        Get detailed status of which files and tile servers are public vs private.

        Single endpoint that returns:
        - Feature assets (photos, videos, point clouds, etc.)
        - Internal tile servers (COG layers)
        - Summary of what's not being checked
        - Last refresh check info
        """
        from geoapi.services.file_location_status import FileLocationStatusService

        logger.info(
            f"Getting public files status for project:{project_id} "
            f"by user:{request.user.username}"
        )

        # Get all feature assets
        # NOTE: Only includes Features with FeatureAssets. Features without assets
        #       (geometry-only, like manually drawn shapes) are excluded from this list.
        #       See WG-600.
        feature_assets = (
            db_session.query(FeatureAsset)
            .join(Feature, Feature.id == FeatureAsset.feature_id)
            .filter(Feature.project_id == project_id)
            .all()
        )


        # Calculate summary counts for context
        total_features = (
            db_session.query(Feature).filter(Feature.project_id == project_id).count()
        )

        count_features_with_assets = (
            db_session.query(Feature.id)
            .join(FeatureAsset, Feature.id == FeatureAsset.feature_id)
            .filter(Feature.project_id == project_id)
            .distinct()
            .count()
        )

        # These features without feature assets are not considered (see WG-600)
        count_features_without_assets = total_features - count_features_with_assets

        # Get all tile servers
        all_tile_servers = TileService.getTileServers(db_session, projectId=project_id)

        # Get all internal tile servers
        # Only internal tile servers are checked (external ones use external URLs
        internal_tile_servers = [ts for ts in all_tile_servers if ts.internal is True]

        # Calculate counts
        total_tile_servers = len(all_tile_servers)
        count_internal_tile_servers = len(internal_tile_servers)
        count_external_tile_servers = total_tile_servers - count_internal_tile_servers

        # Get most recent check
        public_access_check = FileLocationStatusService.get(db_session, project_id)

        # Convert to response models
        feature_assets_status = [
            FeatureAssetModel.model_validate(asset) for asset in feature_assets
        ]

        internal_tile_servers_status = [
            TileServerModel.model_validate(tile_server)
            for tile_server in internal_tile_servers
        ]

        # Build summary
        summary = FileLocationSummary(
            total_features=total_features,
            features_with_assets=count_features_with_assets,  # Considered
            features_without_assets=count_features_without_assets,  # Not considered WG-600
            total_tile_servers=total_tile_servers,
            internal_tile_servers=count_internal_tile_servers,  # Considered
            external_tile_servers=count_external_tile_servers,  # Not considered
        )

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
            featureAssets=feature_assets_status,
            tileServers=internal_tile_servers_status,
            summary=summary,
        )
