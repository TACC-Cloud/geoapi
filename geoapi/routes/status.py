from typing import Literal
from litestar import Controller, get, Request
from litestar.response import Response
from pydantic import BaseModel
from celery.result import AsyncResult
from geoapi.tasks.health import check_worker
from geoapi.log import logging
from geoapi.utils.decorators import not_anonymous_guard

logger = logging.getLogger(__name__)

WORKER_CHECK_TIMEOUT = (
    40  # seconds; request timeout is 60s, leaving buffer for response
)


class StatusResponse(BaseModel):
    status: str


class ComponentStatus(BaseModel):
    status: Literal["ok", "error"]
    detail: str | None = None


class WorkerStatusResponse(BaseModel):
    overall: Literal["ok", "error"]
    components: dict[str, ComponentStatus]


class StatusController(Controller):
    path = "/status"

    @get("/", tags=["status"])
    async def get_status(self, request: Request) -> StatusResponse:
        """Unauthenticated liveness check for load balancer."""
        return StatusResponse(status="OK")

    @get("/complete", tags=["status"], guards=[not_anonymous_guard])
    async def get_status_complete(
        self, request: Request
    ) -> Response[WorkerStatusResponse]:
        """
        Authenticated health check. Submits a Celery task and waits for
        the result, validating worker + Redis connectivity from within the
        worker network.
        """
        # Submit at highest priority so health checks aren't blocked by queued default tasks
        task = check_worker.apply_async(priority=10)
        try:
            result = AsyncResult(task.id).get(timeout=WORKER_CHECK_TIMEOUT)
        except Exception as e:
            logger.error(
                f"Worker health check timed out or failed for user:{request.user.username}: {e}"
            )
            body = WorkerStatusResponse(
                overall="error",
                components={
                    "worker": ComponentStatus(
                        status="error", detail="Worker unavailable or timed out"
                    )
                },
            )
            return Response(content=body, status_code=503)

        body = WorkerStatusResponse(
            overall=result["overall"],
            components={
                k: ComponentStatus(**v) for k, v in result["components"].items()
            },
        )
        status_code = 200 if result["overall"] == "ok" else 503
        if status_code != 200:
            logger.warning(
                f"Worker health check degraded/failed for user:{request.user.username} result:{result}"
            )
        return Response(content=body, status_code=status_code)
