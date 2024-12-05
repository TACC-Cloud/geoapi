import logging
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
