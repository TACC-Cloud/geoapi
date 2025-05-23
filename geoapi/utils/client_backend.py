from geoapi.settings import settings
from geoapi.log import logging
from geoapi.exceptions import AuthenticationIssue, ApiException


logger = logging.getLogger(__name__)


def validate_referrer_url(referrer_url):
    """Check if referrer url is valid.  Raises AuthenticationIssue if not valid."""
    client_url_from_request_url = get_client_url(referrer_url)
    if client_url_from_request_url is None:
        logger.exception(f"Issue with referrer url: {referrer_url}")
        raise AuthenticationIssue(
            "Authentication error: Requesting client not expected"
        )


def get_client_url(url):
    """
    Get requesting client URLs.

    This function checks if the provided URL starts with any of the predefined client URLs. If a match is found,
    it returns the matching client URL. If no match is found, it returns None
    """
    client_urls = [
        "http://localhost:4200/",
        "http://hazmapper.local:4200/",
        "https://hazmapper.tacc.utexas.edu/hazmapper/",
        "https://hazmapper.tacc.utexas.edu/staging/",
        "https://hazmapper.tacc.utexas.edu/dev/",
        "https://hazmapper.tacc.utexas.edu/exp/",
        "https://hazmapper.tacc.utexas.edu/hazmapper-react/",
        "https://hazmapper.tacc.utexas.edu/staging-react/",
        "https://hazmapper.tacc.utexas.edu/dev-react/",
        "https://hazmapper.tacc.utexas.edu/exp-react/",
        "https://hazmapper.tacc.utexas.edu/taggit/",
        "https://hazmapper.tacc.utexas.edu/taggit-staging/",
        "https://hazmapper.tacc.utexas.edu/taggit-dev/",
        "https://hazmapper.tacc.utexas.edu/taggit-exp/",
    ]
    for client in client_urls:
        if url.startswith(client):
            return client.rstrip("/")
    return None


def get_deployed_geoapi_url():
    """
    Get backend url

    This function checks if the provided URL starts with any of the predefined backend URLs. If a match is found,
    it returns the matching client URL. If no match is found, raises API
    """
    geoapi_urls = {
        "local": "http://localhost:8888",
        "production": "https://hazmapper.tacc.utexas.edu/geoapi",
        "staging": "https://hazmapper.tacc.utexas.edu/geoapi-staging",
        "dev": "https://hazmapper.tacc.utexas.edu/geoapi-dev",
        "experimental": "https://hazmapper.tacc.utexas.edu/geoapi-experimental",
        "testing": "http://test:8888",
    }
    if settings.APP_ENV in geoapi_urls:
        return geoapi_urls[settings.APP_ENV]
    else:
        logger.exception(f"Unknown/unsupported APP_ENV:{settings.APP_ENV}")
        raise ApiException(f"Unknown APP_ENV:{settings.APP_ENV}")
