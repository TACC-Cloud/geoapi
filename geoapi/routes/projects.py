import io
from datetime import datetime
from typing import TYPE_CHECKING, Annotated
from pydantic import BaseModel, Field, ConfigDict
from litestar import Controller, get, Request, post, delete, put, Router
from litestar.datastructures import UploadFile
from litestar.params import Body
from litestar.enums import RequestEncodingType
from litestar.exceptions import PermissionDeniedException
from litestar.plugins.sqlalchemy import SQLAlchemyDTO
from litestar.dto import DTOConfig
from uuid import UUID
from geojson_pydantic import Feature as GeoJSONFeature
from geoapi.log import logger
from geoapi.services.features import FeaturesService
from geoapi.services.streetview import StreetviewService
from geoapi.services.point_cloud import PointCloudService
from geoapi.services.projects import ProjectsService
from geoapi.tasks import external_data, streetview
from geoapi.models import Task, Project, Feature, TileServer, Overlay, PointCloud
from geoapi.utils.decorators import (
    project_permissions_allow_public_guard,
    project_permissions_guard,
    project_feature_exists_guard,
    project_point_cloud_exists_guard,
    project_point_cloud_not_processing_guard,
    not_anonymous_guard,
    project_admin_or_creator_permissions_guard,
    check_access_and_get_project,
    is_anonymous,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class OkResponse(BaseModel):
    message: str = "accepted"


class AssetModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    path: str | None = None
    uuid: UUID | None = None
    asset_type: str | None = None
    original_path: str | None = None
    original_name: str | None = None
    display_path: str | None = None


class FeatureModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    geometry: dict
    properties: dict | None = None
    styles: dict | None = None
    assets: list[AssetModel] | None = None


class FeatureReturnDTO(SQLAlchemyDTO[Feature]):
    config = DTOConfig(
        include={
            "id",
            "project_id",
            "geometry",
            "properties",
            "styles",
            "assets",
        }
    )


class FeatureCollectionModel(BaseModel):
    type: str = "FeatureCollection"
    features: list[FeatureModel] | None = None


class ProjectPayloadModel(BaseModel):
    name: str
    description: str
    public: bool | None = None
    system_file: str | None = None
    system_id: str | None = None
    system_path: str | None = None
    watch_content: bool | None = None
    watch_users: bool | None = None


class ProjectUpdatePayloadModel(BaseModel):
    name: str | None = None
    description: str | None = None
    public: bool | None = None


class ProjectDTO(SQLAlchemyDTO[Project]):
    config = DTOConfig(
        include={
            "id",
            "uuid",
            "name",
            "description",
            "public",
            "system_file",
            "system_id",
            "system_path",
            "deletable",
        },
    )


class UserModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    id: int | None = None


class UserPayloadModel(UserModel):
    admin: bool = False


class TaskModel(BaseModel):
    id: int | None = None
    status: str | None = None
    description: str | None = None
    created: datetime = None
    updated: datetime = None


class PointCloudDTO(SQLAlchemyDTO[PointCloud]):
    config = DTOConfig(
        include={
            "id",
            "description",
            "conversion_parameters",
            "files_info",
            "feature_id",
            "task",
            "project_id",
        },
    )


class PointCloudModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    files_info: dict | None = None
    id: int | None = None
    description: str | None = None
    conversion_parameters: str | None = None
    feature_id: int | None = None
    task: TaskModel = None
    project_id: int | None = None


class OverlayDTO(SQLAlchemyDTO[Overlay]):
    config = DTOConfig(
        exclude={"project"},
    )


class OverlayModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: str
    minLon: float
    minLat: float
    maxLon: float
    maxLat: float
    path: str
    project_id: int
    label: str


class TileServerModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    name: str | None = None
    type: str | None = None
    url: str | None = None
    attribution: str | None = None
    tileOptions: dict | None = None
    uiOptions: dict | None = None


class TapisFileUploadModel(BaseModel):
    system_id: str | None = None
    path: str | None = None


class TapisFileModel(BaseModel):
    system: str
    path: str


class TapisSaveFileModel(BaseModel):
    system_id: str
    path: str
    file_name: str
    observable: bool | None = None
    watch_content: bool | None = None


class TapisFileImportModel(BaseModel):
    files: list[TapisFileModel]


class OverlayPostBody(BaseModel):
    label: str
    minLon: float
    minLat: float
    maxLon: float
    maxLat: float


class AddOverlayBody(OverlayPostBody):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    file: UploadFile


class TapisOverlayImportBody(OverlayPostBody):
    system_id: str
    path: str


class ProjectsListingController(Controller):
    path = "/"
    return_dto = ProjectDTO

    @get(
        tags=["projects"],
        operation_id="get_projects",
        description="Get a list of projects",
    )
    def get_projects(self, request: Request, db_session: "Session") -> list[Project]:
        """Get a list of projects for the current user or a specific project by UUID."""
        u = request.user
        uuid_subset = request.query_params.get("uuid", None)
        if uuid_subset:
            logger.info(
                f"Getting a subset of projects for user:{u.username} project_uuid:{uuid_subset}"
            )
            # Check each project and abort if user (authenticated or anonymous) can't access the project
            subset = [
                check_access_and_get_project(
                    request.user,
                    db_session=db_session,
                    uuid=uuid,
                    allow_public_use=True,
                )
                for uuid in uuid_subset.split(",")
            ]
            return subset
        if is_anonymous(u):
            raise PermissionDeniedException(403, "Access denied.")
        logger.info(f"Get all projects for user:{u.username}")
        return ProjectsService.list(db_session, u)

    @post(
        tags=["projects"],
        operation_id="create_project",
        description="Create a new project",
        guards=[not_anonymous_guard],
    )
    def create_project(
        self, request: Request, db_session: "Session", data: ProjectPayloadModel
    ) -> Project:
        """Create a new project."""
        u = request.user
        logger.info("Create project for user:{} : {}".format(u.username, data))
        return ProjectsService.create(db_session, data.model_dump(), u)


class ProjectResourceController(Controller):
    path = "/{project_id:int}/"
    return_dto = ProjectDTO

    @get(
        tags=["projects"],
        operation_id="get_project_by_id",
        description="Get the metadata about a project",
        guards=[project_permissions_allow_public_guard],
    )
    def get_project_by_id(
        self, request: Request, db_session: "Session", project_id: int
    ) -> Project:
        """Get the metadata about a project by its ID."""
        u = request.user
        logger.info(
            "Get metadata project:{} for user:{}".format(project_id, u.username)
        )
        return ProjectsService.get(db_session, project_id=project_id, user=u)

    @delete(
        tags=["projects"],
        operation_id="delete_project",
        description="Delete a project, all associated features and metadata. THIS CANNOT BE UNDONE",
        guards=[project_admin_or_creator_permissions_guard],
    )
    def delete_project(
        self, request: Request, db_session: "Session", project_id: int
    ) -> None:
        """Delete a project by its ID."""
        u = request.user
        # Retrieve the project using the projectId to get its UUID
        project = ProjectsService.get(db_session, project_id=project_id, user=u)
        logger.info(
            "Delete project:{} with project_uuid:{} for user:{}".format(
                project_id, project.uuid, u.username
            )
        )
        ProjectsService.delete(db_session, u, project_id)

    @put(
        tags=["projects"],
        operation_id="update_project",
        description="Update metadata about a project",
        guards=[project_permissions_guard],
    )
    def update_project(
        self,
        request: Request,
        db_session: "Session",
        project_id: int,
        data: ProjectUpdatePayloadModel,
    ) -> Project:
        """Update metadata about a project by its ID."""
        u = request.user
        logger.info("Update project:{} for user:{}".format(project_id, u.username))
        return ProjectsService.update(
            db_session, projectId=project_id, data=data.model_dump()
        )


class ProjectCheckAccessResourceController(Controller):
    path = "/{project_id:int}/check-access/"

    @get(
        tags=["projects"],
        operation_id="check_user_access",
        description="Check if user or guest can access this project",
        guards=[project_permissions_allow_public_guard],
    )
    def check_user_access(self, request: Request, project_id: int) -> OkResponse:
        """Check if user or guest can access this project."""
        # Access granted by `project_permissions_allow_public_guard` — so just
        # returning 200 here
        logger.info(f"User:{request.user.username} has access to project:{project_id}")
        return OkResponse(message="Access granted")


class ProjectUsersResourceController(Controller):
    path = "/{project_id:int}/users/"

    @get(
        tags=["projects"],
        operation_id="get_project_users",
        description="Get users associated with a project",
        guards=[project_permissions_guard],
    )
    def get_project_users(
        self, request: Request, db_session: "Session", project_id: int
    ) -> list[UserModel]:
        """Get users associated with a project."""
        logger.info(
            f"Get users of project:{project_id} for user:{request.user.username}"
        )
        return ProjectsService.getUsers(db_session, project_id)

    @post(
        tags=["projects"],
        operation_id="add_user_to_project",
        summary="Add a user to the project",
        guards=[project_permissions_guard],
        description="Add a user to the project. If `admin` is True then user has full access to the project, "
        "including deleting the entire thing so chose carefully.",
    )
    def add_user_to_project(
        self,
        request: Request,
        db_session: "Session",
        project_id: int,
        data: UserPayloadModel,
    ) -> OkResponse:
        """Add a user to the project."""
        username = data.username
        admin = data.admin
        logger.info(
            "User: {} is adding user:{} to project:{}".format(
                request.user.username, username, project_id
            )
        )
        ProjectsService.addUserToProject(db_session, project_id, username, admin)
        return OkResponse(message="User added successfully")


class ProjectUserResourceController(Controller):
    path = "/{project_id:int}/users/{username:str}/"

    @delete(
        tags=["projects"],
        operation_id="remove_user_from_project",
        description="Remove a user from a project",
        guards=[project_admin_or_creator_permissions_guard],
    )
    def remove_user_from_project(
        self, request: Request, db_session: "Session", project_id: int, username: str
    ) -> None:
        """Remove a user from a project."""
        logger.info(
            "Delete user:{} from project:{} for user:{}".format(
                username, project_id, request.user.username
            )
        )
        ProjectsService.removeUserFromProject(db_session, project_id, username)


class ProjectFeaturesResourceController(Controller):
    path = "/{project_id:int}/features/"

    class ProjectFeaturesResourceModel(BaseModel):
        assetType: str | None = None
        bbox: str | None = Field(
            default=None, description="Bounding box: minLon,minLat,maxLon,maxLat"
        )
        startDate: datetime | None = None
        endDate: datetime | None = None

    @get(
        tags=["projects"],
        operation_id="get_all_features",
        description="GET all the features of a project as GeoJSON",
        guards=[project_permissions_allow_public_guard],
    )
    def get_all_features(
        self,
        request: Request,
        db_session: "Session",
        project_id: int,
        query: ProjectFeaturesResourceModel,
    ) -> FeatureCollectionModel:
        """Get all features of a project as GeoJSON."""
        # Following log is for analytics, see https://confluence.tacc.utexas.edu/display/DES/Hazmapper+Logging
        application = request.headers.get("X-Geoapi-Application", "Unknown")
        is_public_view = request.headers.get("X-Geoapi-IsPublicView", "Unknown")

        prj = ProjectsService.get(db_session, project_id=project_id, user=request.user)
        logger.info(
            f"Get features of project for user:{request.user.username} application:{application}"
            f" public_view:{is_public_view} project_uuid:{prj.uuid} project:{prj.id} tapis_system_id:{prj.system_id} "
            f"tapis_system_path:{prj.system_path}"
        )

        query_params = query.model_dump()
        if query_params.get("bbox"):
            query_params["bbox"] = [
                float(coord) for coord in query_params["bbox"].split(",")
            ]
        return ProjectsService.getFeatures(db_session, project_id, query_params)

    @post(
        tags=["projects"],
        operation_id="add_geojson_feature",
        description="Add a GeoJSON feature to a project",
        guards=[project_permissions_guard],
        return_dto=FeatureReturnDTO,
    )
    def add_geojson_feature(
        self,
        request: Request,
        db_session: "Session",
        project_id: int,
        data: GeoJSONFeature,
    ) -> FeatureModel:
        """Add a GeoJSON feature to a project."""
        logger.info(
            "Add GeoJSON feature to project:{} for user:{}".format(
                project_id, request.user.username
            )
        )
        return FeaturesService.addGeoJSON(db_session, project_id, data.model_dump())


class ProjectFeatureResourceController(Controller):
    path = "/{project_id:int}/features/{feature_id:int}/"

    @get(
        tags=["projects"],
        operation_id="get_feature",
        description="GET a feature of a project as GeoJSON",
        guards=[project_permissions_allow_public_guard],
        return_dto=FeatureReturnDTO,
    )
    def get_feature(
        self, request: Request, db_session: "Session", project_id: int, feature_id: int
    ) -> FeatureModel:
        """Get a feature of a project as GeoJSON."""
        logger.info(
            f"Get feature:{feature_id} of project:{project_id} for user:{request.user.username}"
        )
        return FeaturesService.get(db_session, feature_id)

    @delete(
        tags=["projects"],
        operation_id="delete_feature",
        description="Delete a feature from a project",
        guards=[project_permissions_guard],
    )
    def delete_feature(
        self, request: Request, db_session: "Session", project_id: int, feature_id: int
    ) -> None:
        """Delete a feature from a project."""
        logger.info(
            "Delete feature:{} from project:{} for user:{}".format(
                feature_id, project_id, request.user.username
            )
        )
        FeaturesService.delete(db_session, feature_id)


class ProjectFeaturePropertiesResourceController(Controller):
    path = "/{project_id:int}/features/{feature_id:int}/properties/"

    @post(
        tags=["projects"],
        operation_id="update_feature_properties",
        summary="Update the properties of a feature.",
        description="Update the properties of a feature. This will replace any existing properties previously associated with the feature",
        guards=[project_permissions_guard, project_feature_exists_guard],
        return_dto=FeatureReturnDTO,
    )
    def update_feature_properties(
        self,
        request: Request,
        db_session: "Session",
        project_id: int,
        feature_id: int,
        data: dict,
    ) -> FeatureModel:
        """Update the properties of a feature."""
        logger.info(
            "Update properties of feature:{} in project:{} for user:{}".format(
                feature_id, project_id, request.user.username
            )
        )
        return FeaturesService.setProperties(db_session, feature_id, data)


class ProjectFeatureStylesResourceController(Controller):
    path = "/{project_id:int}/features/{feature_id:int}/styles/"

    @post(
        tags=["projects"],
        operation_id="update_feature_styles",
        summary="Update the styles of a feature.",
        description="Update the styles of a feature. This will replace any styles previously associated with the feature.",
        guards=[project_permissions_guard, project_feature_exists_guard],
        return_dto=FeatureReturnDTO,
    )
    def update_feature_styles(
        self,
        request: Request,
        db_session: "Session",
        project_id: int,
        feature_id: int,
        data: dict,
    ) -> FeatureModel:
        """Update the styles of a feature."""
        logger.info(
            "Update styles for feature:{} in project:{} for user:{}".format(
                feature_id, project_id, request.user.username
            )
        )
        return FeaturesService.setStyles(db_session, feature_id, data)


class ProjectFeaturesCollectionResourceController(Controller):
    path = "/{project_id:int}/features/{feature_id:int}/assets/"

    @post(
        tags=["projects"],
        operation_id="add_feature_asset",
        description="Add a static asset to a collection. Must be an image or video at the moment",
        guards=[project_permissions_guard, project_feature_exists_guard],
        return_dto=FeatureReturnDTO,
    )
    def add_feature_asset(
        self,
        request: Request,
        db_session: "Session",
        project_id: int,
        feature_id: int,
        data: TapisFileUploadModel,
    ) -> FeatureModel:
        """Add a static asset to a feature."""
        system_id = data.system_id
        path = data.path
        u = request.user
        logger.info(
            "Add feature asset to project:{} for user:{}: {}/{}".format(
                project_id, u.username, system_id, path
            )
        )
        return FeaturesService.createFeatureAssetFromTapis(
            db_session, u, project_id, feature_id, system_id, path
        )


class ProjectFeaturesFilsResourceController(Controller):
    path = "/{project_id:int}/features/files/"

    @post(
        tags=["projects"],
        operation_id="uplaod_feature_file",
        description="""
          Add a new feature(s) to a project from a file that has embedded geospatial information.
          Current allowed file types are GeoJSON, georeferenced image (jpeg) or gpx track.
          Any additional key/value pairs in the form will also be placed in the feature(s) metadata""",
        guards=[project_permissions_guard],
        return_dto=FeatureReturnDTO,
    )
    def upload_feature_file(
        self,
        request: Request,
        db_session: "Session",
        project_id: int,
        data: Annotated[
            dict[str, UploadFile], Body(media_type=RequestEncodingType.MULTI_PART)
        ],
    ) -> list[FeatureModel]:
        """Upload a file containing features to a project."""
        file = data.pop("file")
        logger.info(
            "Add feature to project:{} for user:{}: {}".format(
                project_id, request.user.username, file.filename
            )
        )
        return FeaturesService.fromFileObj(db_session, project_id, file, data)


class ProjectFeaturesFileImportResourceController(Controller):
    path = "/{project_id:int}/features/files/import/"

    @post(
        tags=["projects"],
        operation_id="import_files_from_tapis",
        description="""Import a file into a project from Tapis. Current allowed file types are georeferenced image (jpeg), gpx tracks,
        GeoJSON and shape files. This is an asynchronous operation, files will be imported in the background""",
        guards=[project_permissions_guard],
    )
    def import_files_from_tapis(
        self,
        request: Request,
        project_id: int,
        data: TapisFileImportModel,
    ) -> OkResponse:
        """Import files into a project from Tapis."""
        u = request.user
        logger.info(
            "Import feature to project:{} for user:{}: {}".format(
                project_id, u.username, data.files
            )
        )
        for file in data.files:
            external_data.import_file_from_tapis.delay(
                u.id, file.system, file.path, project_id
            )
        return OkResponse(message="Task created for file import")


class ProjectFeaturesClustersResourceController(Controller):
    path = "/{project_id:int}/features/cluster/{num_clusters:int}/"

    @get(
        tags=["projects"],
        operation_id="get_feature_clusters",
        description="""K-Means cluster the features in a project. This returns a FeatureCollection of the centroids with the additional
        property of "count" representing the number of Features that were aggregated into each cluster.""",
        guards=[project_permissions_guard],
    )
    def get_feature_clusters(
        self,
        request: Request,
        db_session: "Session",
        project_id: int,
        num_clusters: int,
    ) -> FeatureCollectionModel:
        """Get feature clusters for a project."""
        logger.info(
            "Get feature clusters for project:{} for user:{} with num_clusters:{}".format(
                project_id, request.user.username, num_clusters
            )
        )
        return FeaturesService.clusterKMeans(db_session, project_id, num_clusters)


class ProjectOverlaysResourceController(Controller):
    path = "/{project_id:int}/overlays/"

    @post(
        tags=["projects"],
        operation_id="add_overlay",
        description="Add a new overlay to a project",
        guards=[project_permissions_guard],
        return_dto=OverlayDTO,
    )
    async def add_overlay(
        self,
        request: Request,
        db_session: "Session",
        project_id: int,
        data: Annotated[
            AddOverlayBody, Body(media_type=RequestEncodingType.MULTI_PART)
        ],
    ) -> Overlay:
        """Add an overlay to a project."""
        file = data.file
        file_bytes = await file.read()
        file_obj = io.BytesIO(file_bytes)

        logger.info(
            "Add overlay to project:{} for user:{}: {}".format(
                project_id, request.user.username, file.filename
            )
        )

        bounds = [data.minLon, data.minLat, data.maxLon, data.maxLat]
        label = data.label
        return FeaturesService.addOverlay(
            db_session, project_id, file_obj, bounds, label
        )

    @get(
        tags=["projects"],
        operation_id="get_overlays",
        description="Get a list of all the overlays associated with the current map project.",
        guards=[project_permissions_allow_public_guard],
    )
    def get_overlays(
        self, request: Request, db_session: "Session", project_id: int
    ) -> list[OverlayModel]:
        """Get a list of overlays for a project."""
        logger.info(
            "Get overlays for project:{} for user:{}".format(
                project_id, request.user.username
            )
        )
        return FeaturesService.getOverlays(db_session, project_id)


class ProjectOverlaysImportResourceController(Controller):
    path = "/{project_id:int}/overlays/import/"

    @post(
        tags=["projects"],
        operation_id="import_overlay_from_tapis",
        description="Import an overlay from Tapis into a project.",
        guards=[project_permissions_guard],
        return_dto=OverlayDTO,
    )
    def import_overlay_from_tapis(
        self,
        request: Request,
        db_session: "Session",
        project_id: int,
        data: TapisOverlayImportBody,
    ) -> Overlay:
        """Import an overlay from Tapis into a project."""
        u = request.user
        logger.info(
            "Import overlay to project:{} for user:{}: {}".format(
                project_id, u.username, data
            )
        )
        system_id = data.system_id
        path = data.path
        label = data.label
        bounds = [data.minLon, data.minLat, data.maxLon, data.maxLat]
        return FeaturesService.addOverlayFromTapis(
            db_session, u, project_id, system_id, path, bounds, label
        )


class ProjectOverlayResourceController(Controller):
    path = "/{project_id:int}/overlays/{overlay_id:int}/"

    @delete(
        tags=["projects"],
        operation_id="remove_overlay",
        description="Remove an overlay from a project",
        guards=[project_permissions_guard],
    )
    def remove_overlay(
        self, request: Request, db_session: "Session", project_id: int, overlay_id: int
    ) -> None:
        """Remove an overlay from a project."""
        logger.info(
            "Delete overlay:{} in project:{} for user:{}".format(
                overlay_id, project_id, request.user.username
            )
        )
        FeaturesService.deleteOverlay(db_session, project_id, overlay_id)


class ProjectStreetviewResourceController(Controller):
    path = "/{project_id:int}/streetview/"

    @post(
        tags=["projects"],
        operation_id="add_streetview_sequence_to_feature",
        description="""Add a streetview sequence to a project feature.
        This is an asynchronous operation, streetview data will be processed in the background""",
        guards=[project_permissions_guard],
    )
    def add_streetview_sequence_to_feature(
        self,
        request: Request,
        db_session: "Session",
        project_id: int,
        data: dict[str, dict],
    ) -> TaskModel:
        """Add streetview data to a project."""
        logger.info(
            "Add streetview sequence to project features:{} for user:{}".format(
                project_id, request.user.username
            )
        )
        sequenceId = data["sequenceId"]
        token = data["token"]["token"]
        return streetview.process_streetview_sequences(
            db_session, project_id, sequenceId, token
        )


class ProjectStreetviewFeatureResourceController(Controller):
    path = "/{project_id:int}/streetview/{feature_id:int}/"

    @get(
        tags=["projects"],
        operation_id="get_streetview_sequence_from_feature",
        description="Get streetview sequence from a project feature",
        guards=[project_permissions_guard],
        return_dto=FeatureReturnDTO,
    )
    def get_streetview_sequence_from_feature(
        self,
        request: Request,
        db_session: "Session",
        project_id: int,
        feature_id: int,
    ) -> FeatureModel:
        """Get streetview sequence from a project feature."""
        logger.info(
            "Get streetview sequence from project features:{} for user:{}".format(
                project_id, request.user.username
            )
        )
        return StreetviewService.sequenceFromFeature(db_session, feature_id)


class ProjectPointCloudsResourceController(Controller):
    path = "/{project_id:int}/point-cloud/"

    @get(
        tags=["projects"],
        operation_id="get_all_point_clouds",
        description="Get a listing of all the points clouds of a project.",
        guards=[project_permissions_allow_public_guard],
        return_dto=PointCloudDTO,
    )
    def get_all_point_clouds(
        self,
        request: Request,
        db_session: "Session",
        project_id: int,
    ) -> list[PointCloud]:
        """Get a listing of all the point clouds of a project."""
        logger.info(
            "Get point clouds for project:{} for user:{}".format(
                project_id, request.user.username
            )
        )
        return PointCloudService.list(db_session, project_id)

    @post(
        tags=["projects"],
        operation_id="add_point_cloud",
        description="Add a point cloud to a project.",
        guards=[project_permissions_guard],
        return_dto=PointCloudDTO,
    )
    def add_point_cloud(
        self,
        request: Request,
        db_session: "Session",
        project_id: int,
        data: PointCloudModel,
    ) -> PointCloud:
        """Add a point cloud to a project."""
        logger.info(
            "Add point cloud to project:{} for user:{}".format(
                project_id, request.user.username
            )
        )
        return PointCloudService.create(
            database_session=db_session,
            projectId=project_id,
            user=request.user,
            data=data.model_dump(),
        )


class ProjectPointCloudResourceController(Controller):
    path = "/{project_id:int}/point-cloud/{point_cloud_id:int}/"

    @get(
        tags=["projects"],
        operation_id="get_point_cloud",
        description="Get point cloud of a project by its ID.",
        guards=[project_permissions_allow_public_guard],
        return_dto=PointCloudDTO,
    )
    def get_point_cloud(
        self,
        request: Request,
        db_session: "Session",
        project_id: int,
        point_cloud_id: int,
    ) -> PointCloud:
        """Get point cloud of a project by its ID."""
        logger.info(
            "Get point cloud:{} in project:{} for user:{}".format(
                point_cloud_id, project_id, request.user.username
            )
        )
        return PointCloudService.get(db_session, point_cloud_id)

    @put(
        tags=["projects"],
        operation_id="update_point_cloud",
        description="Update point cloud of a project by its ID.",
        guards=[
            project_permissions_guard,
            project_point_cloud_exists_guard,
            project_point_cloud_not_processing_guard,
        ],
        return_dto=PointCloudDTO,
    )
    def update_point_cloud(
        self,
        request: Request,
        db_session: "Session",
        project_id: int,
        point_cloud_id: int,
        data: PointCloudModel,
    ) -> PointCloud:
        """Update point cloud of a project by its ID."""
        logger.info(
            "Update point cloud:{} in project:{} for user:{}".format(
                point_cloud_id, project_id, request.user.username
            )
        )
        # TODO consider adding status to point cloud as we aren't returning task
        return PointCloudService.update(
            database_session=db_session,
            pointCloudId=point_cloud_id,
            data=data.model_dump(exclude_defaults=True),
        )

    @delete(
        tags=["projects"],
        operation_id="delete_point_cloud",
        description="""Delete point cloud, all associated point cloud files will be deleted
        (however associated feature and feature asset will not be deleted). THIS CANNOT BE UNDONE""",
        guards=[
            project_permissions_guard,
            project_point_cloud_exists_guard,
            project_point_cloud_not_processing_guard,
        ],
    )
    def delete_point_cloud(
        self,
        request: Request,
        db_session: "Session",
        project_id: int,
        point_cloud_id: int,
    ) -> None:
        """Delete point cloud of a project by its ID."""
        logger.info(
            "Delete point cloud:{} in project:{} for user:{}".format(
                point_cloud_id, project_id, request.user.username
            )
        )
        PointCloudService.delete(db_session, point_cloud_id)


class ProjectPointCloudsFileImportResourceController(Controller):
    path = "/{project_id:int}/point-cloud/{point_cloud_id:int}/import/"

    @post(
        tags=["projects"],
        operation_id="import_point_cloud_file_from_tapis",
        description="""Import a point cloud file into a project from Tapis. Current allowed file types are las and laz. This is an
        asynchronous operation, files will be imported in the background.""",
        guards=[
            project_permissions_guard,
            project_point_cloud_exists_guard,
            project_point_cloud_not_processing_guard,
        ],
    )
    def import_point_cloud_file_from_tapis(
        self,
        request: Request,
        project_id: int,
        point_cloud_id: int,
        data: TapisFileImportModel,
    ) -> OkResponse:
        """Import a point cloud file into a project from Tapis."""
        u = request.user
        files = data.files
        logger.info(
            "Import file(s) to a point cloud:{} in project:{} for user:{}: {}".format(
                point_cloud_id, project_id, u.username, files
            )
        )

        for file in files:
            PointCloudService.check_file_extension(file.path)

        external_data.import_point_clouds_from_tapis.delay(u.id, files, point_cloud_id)
        return OkResponse(message="Task created for point cloud import")


class ProjectTasksResourceController(Controller):
    path = "/{project_id:int}/tasks/"

    @get(
        tags=["projects"],
        operation_id="get_project_tasks",
        description="Get a listing of all the tasks of a project",
        guards=[project_permissions_guard],
    )
    def get_project_tasks(
        self, request: Request, db_session: "Session", project_id: int
    ) -> list[TaskModel]:
        """Get a listing of all the tasks of a project."""
        logger.info(
            "Get tasks for project:{} for user:{}".format(
                project_id, request.user.username
            )
        )
        return db_session.query(Task).all()


class ProjectTileServersResourceController(Controller):
    path = "/{project_id:int}/tile-servers/"

    @post(
        tags=["projects"],
        operation_id="add_tile_server",
        description="Add a new tile server to a project.",
        guards=[project_permissions_guard],
    )
    def add_tile_server(
        self,
        request: Request,
        db_session: "Session",
        project_id: int,
        data: TileServerModel,
    ) -> TileServerModel:
        """Add a tile server to a project."""
        logger.info(
            "Add tile server to project:{} for user:{}: {}".format(
                project_id, request.user.username, data.name
            )
        )
        return FeaturesService.addTileServer(db_session, project_id, data.model_dump())

    @get(
        tags=["projects"],
        operation_id="get_tile_servers",
        description="Get a list of all the tile servers associated with the current map project.",
        guards=[project_permissions_allow_public_guard],
    )
    def get_tile_servers(
        self, request: Request, db_session: "Session", project_id: int
    ) -> list[TileServer]:
        """Get a list of tile servers for a project."""
        logger.info(
            "Get tile servers for project:{} for user:{}".format(
                project_id, request.user.username
            )
        )
        return FeaturesService.getTileServers(db_session, project_id)


class ProjectTileServerResourceController(Controller):
    path = "/{project_id:int}/tile-servers/{tile_server_id:int}/"

    @delete(
        tags=["projects"],
        operation_id="delete_tile_server",
        description="Delete a tile server from a project.",
        guards=[project_permissions_guard],
    )
    def delete_tile_server(
        self,
        request: Request,
        db_session: "Session",
        project_id: int,
        tile_server_id: int,
    ) -> None:
        """Delete a tile server from a project."""
        logger.info(
            "Delete tile server:{} in project:{} for user:{}".format(
                tile_server_id, project_id, request.user.username
            )
        )
        FeaturesService.deleteTileServer(db_session, tile_server_id)

    @put(
        tags=["projects"],
        operation_id="update_tile_server",
        description="Update metadata about a tile server",
        guards=[project_permissions_guard],
    )
    def update_tile_server(
        self,
        request: Request,
        db_session: "Session",
        project_id: int,
        tile_server_id: int,
        data: dict[str, dict],
    ) -> TileServerModel:
        """Update metadata about a tile server."""
        logger.info(
            "Update tile server:{} in project:{} for user:{}".format(
                tile_server_id, project_id, request.user.username
            )
        )
        return FeaturesService.updateTileServer(
            database_session=db_session, tileServerId=tile_server_id, data=data
        )


def feature_enc_hook(feature: Feature) -> FeatureModel:
    """Encode Feature to a dictionary."""

    return FeatureModel(
        id=feature.id,
        project_id=feature.project_id,
        geometry=feature.geometry,
        properties=feature.properties,
        styles=feature.styles,
        assets=feature.assets,
    )


projects_router = Router(
    path="/projects",
    route_handlers=[
        ProjectsListingController,
        ProjectResourceController,
        ProjectCheckAccessResourceController,
        ProjectUsersResourceController,
        ProjectUserResourceController,
        ProjectFeaturesResourceController,
        ProjectFeatureResourceController,
        ProjectFeaturePropertiesResourceController,
        ProjectFeatureStylesResourceController,
        ProjectFeaturesCollectionResourceController,
        ProjectFeaturesFilsResourceController,
        ProjectFeaturesFileImportResourceController,
        ProjectFeaturesClustersResourceController,
        ProjectOverlaysResourceController,
        ProjectOverlaysImportResourceController,
        ProjectOverlayResourceController,
        ProjectStreetviewResourceController,
        ProjectStreetviewFeatureResourceController,
        ProjectPointCloudsResourceController,
        ProjectPointCloudResourceController,
        ProjectPointCloudsFileImportResourceController,
        ProjectTasksResourceController,
        ProjectTileServersResourceController,
        ProjectTileServerResourceController,
    ],
    type_encoders={Feature: feature_enc_hook},
)
