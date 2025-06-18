from litestar import Controller, get, Request
from pydantic import BaseModel
from geoapi.log import logging

logger = logging.getLogger(__name__)


class StatusResponse(BaseModel):
    status: str


class StatusController(Controller):
    path = "/status"

    @get("/", tags=["status"])
    async def get_status(self, request: Request) -> StatusResponse:
        return StatusResponse(status="OK")
