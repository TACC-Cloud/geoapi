from pydantic import BaseModel, ConfigDict
from dateutil import parser, tz
from datetime import datetime
from typing import TYPE_CHECKING
from litestar import Controller, get, delete, Request
from geoapi.log import logging
from geoapi.utils.decorators import jwt_decoder_prehandler, not_anonymous_guard
from geoapi.services.notifications import NotificationsService

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def utc_datetime(value):
    dt = parser.parse(value)
    dt = dt.replace(tzinfo=tz.UTC)
    return dt


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    message: str
    created: datetime
    viewed: bool
    id: int


class ProgressNotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    message: str
    progress: int
    uuid: str
    created: datetime
    viewed: bool
    id: int
    logs: dict


class OkResponse(BaseModel):
    message: str = "accepted"


class NotificationsQuery(BaseModel):
    startDate: datetime | None = None


class NotificationsController(Controller):
    path = "/notifications"
    before_request = jwt_decoder_prehandler

    @get(
        "/",
        tags=["notifications"],
        operation_id="get_notifications",
        description="Get a list of notifications",
        guards=[not_anonymous_guard],
    )
    def get_notifications(
        self, request: Request, query: NotificationsQuery, db_session: "Session"
    ) -> list[NotificationResponse]:
        """Get a list of notifications."""
        u = request.user
        return NotificationsService.get(db_session, u, query.model_dump())

    @get(
        "/progress",
        tags=["notifications"],
        operation_id="get_progress_notifications",
        description="Get a list of progress notifications",
    )
    def get_progress_notifications(
        self, request: Request, db_session: "Session"
    ) -> list[ProgressNotificationResponse]:
        """Get a list of progress notifications."""
        u = request.user
        return NotificationsService.getProgress(db_session, u)

    @delete(
        "/progress",
        tags=["notifications"],
        operation_id="delete_done_progress_notifications",
        description="Delete all done progress notifications",
    )
    def delete_done_progress_notifications(self, db_session: "Session") -> None:
        """Delete all done progress notifications."""
        NotificationsService.deleteAllDoneProgress(db_session)

    @get(
        "/progress/{progressUUID: str}",
        tags=["notifications"],
        operation_id="get_progress_notification_id",
        description="Get a specific progress notification",
    )
    def get_progress_notification_id(
        self, progressUUID: str, db_session: "Session"
    ) -> ProgressNotificationResponse:
        """Get a specific progress notification."""
        return NotificationsService.getProgressUUID(db_session, progressUUID)

    @delete(
        "/progress/{progressUUID: str}",
        tags=["notifications"],
        operation_id="delete_progress_notification_id",
        description="Delete a specific progress notification",
    )
    def delete_progress_notification_id(
        self, progressUUID: str, db_session: "Session"
    ) -> None:
        """Delete a specific progress notification."""
        NotificationsService.deleteProgress(db_session, progressUUID)
