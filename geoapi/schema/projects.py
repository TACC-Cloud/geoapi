from datetime import datetime
from pydantic import BaseModel, ConfigDict
from litestar.datastructures import UploadFile
from litestar.plugins.sqlalchemy import SQLAlchemyDTO
from litestar.dto import DTOConfig
from uuid import UUID

from geoapi.models import Task, Project, Feature, TileServer, Overlay, PointCloud, User
from geoapi.schema.tapis import TapisFilePath


class OkResponse(BaseModel):
    message: str = "accepted"


class FeatureAssetModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    feature_id: int
    path: str | None = None
    uuid: UUID
    asset_type: str | None = None
    original_system: str | None = None
    original_path: str | None = None
    original_name: str | None = None
    display_path: str | None = None
    current_system: str | None = None
    current_path: str | None = None
    designsafe_project_id: str | None = None
    last_public_system_check: datetime | None = None
    is_on_public_system: bool | None = None


class FeatureModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    geometry: dict
    properties: dict | None = None
    styles: dict | None = None
    assets: list[FeatureAssetModel] | None = None


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
            "designsafe_project_id",
            "deletable",
        },
    )


class UserDTO(SQLAlchemyDTO[User]):
    config = DTOConfig(
        include={
            "id",
            "username",
        }
    )


class UserModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    id: int | None = None


class UserPayloadModel(UserModel):
    admin: bool = False


class TaskDTO(SQLAlchemyDTO[Task]):
    model_config = ConfigDict(from_attributes=True)
    config = DTOConfig(
        # skipping process_id
        include={
            "id",
            "status",
            "description",
            "project_id",
            "latest_message",
            "created",
            "updated",
        },
    )


class TaskModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    status: str | None = None
    description: str | None = None
    project_id: int | None = None
    latest_message: str | None = None
    created: datetime | None = None
    updated: datetime | None = None


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


class TileServerDTO(SQLAlchemyDTO[TileServer]):
    config = DTOConfig(
        include={
            "id",
            "name",
            "type",
            "kind",
            "internal",
            "uuid",
            "url",
            "attribution",
            "tileOptions",
            "uiOptions",
            # File location tracking fields (from FileLocationTrackingMixin)
            "original_system",
            "original_path",
            "current_system",
            "current_path",
            "designsafe_project_id",
            "is_on_public_system",
            "last_public_system_check",
        }
    )


class TileServerModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    name: str | None = None
    type: str | None = None
    kind: str | None = None
    internal: bool | None = None
    uuid: UUID | None = None
    url: str | None = None
    attribution: str | None = None
    tileOptions: dict | None = None
    uiOptions: dict | None = None

    # File location tracking fields (from FileLocationTrackingMixin)
    original_system: str | None = None
    original_path: str | None = None
    current_system: str | None = None
    current_path: str | None = None
    is_on_public_system: bool | None = None
    designsafe_project_id: str | None = None
    last_public_system_check: datetime | None = None


# TODO: replace with TapisFilePath (and update client software)
class TapisFileUploadModel(BaseModel):
    system_id: str | None = None
    path: str | None = None


class TapisSaveFileModel(BaseModel):
    system_id: str
    path: str
    file_name: str
    observable: bool | None = None
    watch_content: bool | None = None


class TapisFileImportModel(BaseModel):
    files: list[TapisFilePath]


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
