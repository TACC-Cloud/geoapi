import logging
import uuid
from hashlib import sha256
from geoapi.settings import settings


logging.basicConfig(
    format="%(asctime)s :: %(levelname)s :: [%(filename)s:%(lineno)d] :: %(message)s",
    level=logging.INFO,
)


logger = logging.getLogger("geoapi")
logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
formatter = logging.Formatter(
    "%(asctime)s :: %(levelname)s :: [%(filename)s:%(lineno)d] :: %(message)s"
)
for h in logger.handlers:
    h.setFormater(formatter)


def guid_filter(record: logging.LogRecord) -> bool:
    """Log filter that adds a guid to each entry"""

    record.logGuid = uuid.uuid4().hex
    if record.sessionId is not None:
        record.sessionId = sha256(record.sessionId.encode()).hexdigest()
    return True


metrics = logging.getLogger("metrics")
metrics.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(
    logging.Formatter(
        "[METRICS] %(levelname)s %(module)s %(name)s.%(funcName)s:%(lineno)s:"
        " %(message)s user=%(user)s sessionId=%(sessionId)s op=%(operation)s"
        " info=%(info)s timestamp=%(asctime)s trackingId=portals.%(sessionId)s guid=%(logGuid)s portal=hazmapper tenant=designsafe"
    )
)
ch.addFilter(guid_filter)
metrics.addHandler(ch)
