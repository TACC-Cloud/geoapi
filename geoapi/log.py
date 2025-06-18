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


def get_logger(mod_name: str) -> logging.Logger:
    """Return logger object."""
    mod_format = (
        "%(asctime)s :: %(levelname)s :: [%(filename)s:%(lineno)d] :: %(message)s"
    )
    mod_logger = logging.getLogger(mod_name)
    # Writes to stdout
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(mod_format))
    logger.addHandler(ch)
    return mod_logger
