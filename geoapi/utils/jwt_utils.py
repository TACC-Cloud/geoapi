from typing import Dict
from geoapi.log import logging

logger = logging.getLogger(__name__)


def get_jwt(headers: Dict) -> str:
    """
    Extract the jwt from the header

    :param headers: Dict
    :return: jwt
    """
    if "X-Tapis-Token" in headers:
        return headers["X-Tapis-Token"]
    else:
        raise ValueError("No JWT could be found")
