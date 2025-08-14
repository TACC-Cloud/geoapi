from typing import TYPE_CHECKING
from pydantic import BaseModel
from litestar import post, Request, Controller
from litestar.channels import ChannelsPlugin
from geoapi.services.notifications import NotificationsService
from geoapi.utils.decorators import not_anonymous_guard

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TaskStatusWebhookData(BaseModel):
    task_id: str
    status: str
    message: str


class TaskStatusWebhookController(Controller):
    path = "/api/webhooks/task-update"

    @post(
        "",
        operation_id="task_status_webhook",
        description="Handle task status updates from Celery.",
        guards=[not_anonymous_guard],
    )
    async def webhook(
        self,
        db_session: "Session",
        request: Request,
        data: TaskStatusWebhookData,
        channels: ChannelsPlugin,
    ) -> None:
        user = request.user

        NotificationsService.create(
            db_session, user, data.status, data.message, channels
        )
