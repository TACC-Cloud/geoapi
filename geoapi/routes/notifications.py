from pydantic import BaseModel, field_validator
from dateutil import parser, tz
from datetime import datetime
from typing import TYPE_CHECKING
from litestar import Controller, get, delete, Request
from litestar.plugins.sqlalchemy import SQLAlchemyDTO
from litestar.dto import DTOConfig
from geoapi.log import logging
from geoapi.utils.decorators import not_anonymous_guard
from geoapi.services.notifications import (
    NotificationsService,
    Notification,
    ProgressNotification,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def utc_datetime(value):
    dt = parser.parse(value)
    dt = dt.replace(tzinfo=tz.UTC)
    return dt


class NotificationDTO(SQLAlchemyDTO[Notification]):
    config = DTOConfig(exclude={"username", "tenant_id"})


class ProgressNotificationDTO(SQLAlchemyDTO[ProgressNotification]):
    config = DTOConfig(exclude={"user_id", "username", "tenant_id"})


class OkResponse(BaseModel):
    message: str = "accepted"


class NotificationsQuery(BaseModel):
    startDate: datetime | str | None = None

    @field_validator("startDate", mode="before")
    @classmethod
    def validate_start_date(cls, value: datetime | str | None) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            # Accept ISO8601 and fix legacy " 00:00" if needed
            value = value.replace(" 00:00", "+00:00")
            return utc_datetime(value)
        raise ValueError("Invalid startDate format")


class NotificationsController(Controller):
    path = "/notifications"

    @get(
        "/",
        tags=["notifications"],
        operation_id="get_notifications",
        description="Get a list of notifications",
        guards=[not_anonymous_guard],
        return_dto=NotificationDTO,
    )
    def get_notifications(
        self, request: Request, query: NotificationsQuery, db_session: "Session"
    ) -> list[Notification]:
        """Get a list of notifications."""
        u = request.user
        return NotificationsService.get(db_session, u, query.model_dump())

    @get(
        "/progress",
        tags=["notifications"],
        operation_id="get_progress_notifications",
        description="Get a list of progress notifications",
        return_dto=ProgressNotificationDTO,
    )
    def get_progress_notifications(
        self, request: Request, db_session: "Session"
    ) -> list[ProgressNotification]:
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
        return_dto=ProgressNotificationDTO,
    )
    def get_progress_notification_id(
        self, progressUUID: str, db_session: "Session"
    ) -> ProgressNotification:
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
