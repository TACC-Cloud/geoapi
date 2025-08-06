"""
Streetview API Endpoints

This module defines the API endpoints for managing Streetview services, instances,
sequences, and organizations.

**Note:** Currently, only the 'mapillary' service is supported. The API was originally
designed to support both Mapillary and Google Street View, which is why it follows
this structure.
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict
from litestar import Controller, get, Request, post, delete, put
from typing import TYPE_CHECKING
from geoapi.services.streetview import StreetviewService
from geoapi.tasks import streetview
from geoapi.log import logging

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class StreetviewServiceParams(BaseModel):
    service: str | None = None
    service_user: str | None = None
    token: str | None = None


class OkResponse(BaseModel):
    message: str = "accepted"


class TapisFile(BaseModel):
    system: str
    path: str


class TapisFolderImport(BaseModel):
    service: TapisFile
    system_id: str
    path: str


class StreetviewSequence(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    streetview_instance_id: int
    start_date: datetime | None = None  # rfc822
    end_date: datetime | None = None  # rfc822
    bbox: str | None = None
    sequence_id: str | None = None
    organization_id: str | None = None


class StreetviewOrganization(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    streetview_id: int | None = None
    name: str | None = None
    slug: str | None = None
    key: str | None = None


class StreetviewInstance(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    streetview_id: int
    system_id: str
    path: str
    sequences: list[StreetviewSequence] | None = None


class Streetview(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    token: str
    token_expires_at: str
    service: str
    service_user: str
    organizations: list[StreetviewOrganization] | None = None


class StreetviewController(Controller):
    path = "streetview"

    @get(
        "/services",
        operation_id="get_streetview_service_resources",
        description="Get all streetview service objects for a user",
    )
    def get_streetview_service_resources(
        self, request: Request, db_session: "Session"
    ) -> list[Streetview]:
        u = request.user
        logger.info("Get all streetview objects user:{}".format(u.username))
        return StreetviewService.list(db_session, u)

    @post(
        "/services",
        operation_id="create_streetview_service_resource",
        description="Create streetview service object for a user",
    )
    def create_streetview_service_resource(
        self, request: Request, db_session: "Session", data: StreetviewServiceParams
    ) -> Streetview:
        u = request.user
        service = data.service
        logger.info(
            "Create streetview object for user:{} and service:{}".format(
                u.username, service
            )
        )
        return StreetviewService.create(db_session, u, data.model_dump())

    @get(
        "/services/<service>/",
        operation_id="get_streetview_service_resource",
        description="Get a streetview service resource by service name",
    )
    def get_streetview_service_resource(
        self, request: Request, db_session: "Session", service: str
    ) -> Streetview:
        u = request.user
        logger.info(
            "Get streetview service object for service:{} for user:{}".format(
                service, u.username
            )
        )
        return StreetviewService.getByService(db_session, u, service)

    @delete(
        "/services/<service>/",
        operation_id="delete_streetview_service_resource",
        description="Delete a streetview service resource by service name",
    )
    def delete_streetview_service_resource(
        self, request: Request, db_session: "Session", service: str
    ) -> None:
        u = request.user
        logger.info(
            "Delete streetview object for service:{} for user:{}".format(
                service, u.username
            )
        )
        StreetviewService.deleteByService(db_session, u, service)

    @put(
        "/services/<service>/",
        operation_id="update_streetview_service_resource",
        description="Update streetview service resource for a user by service name",
    )
    def update_streetview_service_resource(
        self,
        request: Request,
        db_session: "Session",
        service: str,
        data: StreetviewServiceParams,
    ) -> Streetview:
        u = request.user
        logger.info(
            "Update streetview service resource for service:{} user:{}".format(
                service, u.username
            )
        )
        return StreetviewService.updateByService(
            db_session, u, service, data.model_dump()
        )

    @get(
        "/services/<service>/organization/", operation_id="get_streetview_organizations"
    )
    def get_streetview_organizations(
        self, request: Request, db_session: "Session", service: str
    ) -> list[StreetviewOrganization]:
        u = request.user
        logger.info(
            "Get streetview organizations for service:{} user:{}".format(
                service, u.username
            )
        )
        return StreetviewService.getAllOrganizations(db_session, u, service)

    @post(
        "/services/<service>/organization/",
        operation_id="create_streetview_organization",
    )
    def create_streetview_organization(
        self,
        request: Request,
        db_session: "Session",
        service: str,
        data: StreetviewOrganization,
    ) -> StreetviewOrganization:
        u = request.user
        logger.info(
            "Create streetview organization for service:{} user:{}".format(
                service, u.username
            )
        )
        return StreetviewService.createOrganization(
            db_session, u, service, data.model_dump()
        )

    @delete(
        "/services/<service>/organization/<organization_id>/",
        operation_id="delete_streetview_organization",
        description="Delete organization from streetview service resource",
    )
    def delete_streetview_organization(
        self,
        request: Request,
        db_session: "Session",
        service: str,
        organization_id: int,
    ) -> None:
        u = request.user
        logger.info(
            "Delete streetview organization for service:{} user:{} organization_id:{}".format(
                service, u.username, organization_id
            )
        )
        StreetviewService.deleteOrganization(db_session, organization_id)

    @put(
        "/services/<service>/organization/<organization_id>/",
        operation_id="update_streetview_organization",
        description="Update organization from streetview service resource",
    )
    def update_streetview_organization(
        self,
        request: Request,
        db_session: "Session",
        service: str,
        organization_id: int,
        data: StreetviewOrganization,
    ) -> StreetviewOrganization:
        u = request.user
        logger.info(
            "Update streetview organization for service:{} user:{} organization_id:{}".format(
                service, u.username, organization_id
            )
        )
        return StreetviewService.updateOrganization(
            db_session, organization_id, data.model_dump()
        )

    @delete(
        "/instances/<instance_id>/",
        operation_id="delete_streetview_instance",
        description="Delete streetview instance",
    )
    def delete_streetview_instance(
        self, request: Request, db_session: "Session", instance_id: int
    ) -> None:
        u = request.user
        logger.info(
            "Delete streetview instance for user:{} instance_id:{}".format(
                u.username, instance_id
            )
        )
        StreetviewService.deleteInstance(db_session, instance_id)

    @post(
        "/sequences/",
        operation_id="add_streetview_sequence",
        description="Add sequences to streetview instance",
    )
    def add_streetview_sequence(
        self, request: Request, db_session: "Session", data: StreetviewSequence
    ) -> None:
        u = request.user
        logger.info(
            "Add streetview sequence for user:{} sequence_id:{}".format(
                u.username, data.sequence_id
            )
        )
        StreetviewService.addSequenceToInstance(db_session, u, data.model_dump())

    @get(
        "/sequences/<sequence_id>/",
        operation_id="get_streetview_sequence",
        description="Get a streetview service's sequence",
    )
    def get_streetview_sequence(
        self, request: Request, db_session: "Session", sequence_id: str
    ) -> StreetviewSequence:
        u = request.user
        logger.info(
            "Get streetview sequence of id:{} for user:{}".format(
                sequence_id, u.username
            )
        )
        return StreetviewService.getSequenceFromId(db_session, sequence_id)

    @delete(
        "/sequences/<sequence_id>/",
        operation_id="delete_streetview_sequence",
        description="Delete a streetview service's sequence",
    )
    def delete_streetview_sequence(
        self, request: Request, db_session: "Session", sequence_id: int
    ) -> None:
        u = request.user
        logger.info(
            "Delete streetview sequence of id:{} for user:{}".format(
                sequence_id, u.username
            )
        )
        StreetviewService.deleteSequence(db_session, sequence_id)

    @put(
        "/sequences/<sequence_id>/",
        operation_id="update_streetview_sequence",
        description="Update a streetview service's sequence",
    )
    def update_streetview_sequence(
        self,
        request: Request,
        db_session: "Session",
        sequence_id: int,
        data: StreetviewOrganization,
    ) -> StreetviewSequence:
        u = request.user
        logger.info(
            "Update streetview sequence of id:{} for user:{}".format(
                sequence_id, u.username
            )
        )
        return StreetviewService.updateSequence(
            db_session, sequence_id, data.model_dump()
        )

    @post(
        "/publish/",
        operation_id="publish_files_to_streetview",
        description="Publish files to streetview",
        summary="""Import all files in a directory into a project from Tapis.
        The files should contain GPano metadata for compatibility with streetview services.
        This is an asynchronous operation, files will be imported in the background""",
    )
    def publish_files_to_streetview(
        self, request: Request, db_session: "Session", data: TapisFolderImport
    ) -> OkResponse:
        u = request.user
        logger.info("Publish images to streetview for user:{}".format(u.username))
        streetview.publish(db_session, u, data.model_dump())
        return OkResponse(message="accepted")
