import redis
from redis.exceptions import RedisError
from sqlalchemy import text
from geoapi.celery_app import app
from geoapi.settings import settings
from geoapi.db import create_task_session
from geoapi.log import logging

logger = logging.getLogger(__name__)


def check_redis() -> dict:
    try:
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)
        r.ping()
        return {"status": "ok", "detail": None}
    except RedisError as e:
        logger.error(f"Worker health check: Redis problem: {e}")
        return {"status": "error", "detail": str(e)}


def check_database() -> dict:
    try:
        with create_task_session() as session:
            session.execute(text("SELECT 1"))
        return {"status": "ok", "detail": None}
    except Exception as e:
        logger.error(f"Worker health check: DB problem: {e}")
        return {"status": "error", "detail": str(e)}


def derive_overall_status(components: dict) -> str:
    statuses = [c["status"] for c in components.values()]
    if all(s == "ok" for s in statuses):
        return "ok"
    return "error"


@app.task
def check_worker() -> dict:
    components = {
        "redis": check_redis(),
        "database": check_database(),
    }
    overall = derive_overall_status(components)
    return {"overall": overall, "components": components}
