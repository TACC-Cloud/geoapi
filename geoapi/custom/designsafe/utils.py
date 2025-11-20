from geoapi.log import logger
from geoapi.settings import settings
from geoapi.models import User


DESIGNSAFE_PROJECT_ID_CACHE = {}


def extract_project_uuid(system_id: str) -> str | None:
    if system_id.startswith("project-"):
        return system_id.removeprefix("project-")
    return None


def is_designsafe_project(system_id: str) -> bool:
    if system_id and system_id.startswith("project-"):
        return True
    return False


def get_designsafe_project_data(database_session, user: User, system_id: str) -> dict:
    """
    Get project data for a certain system

    :param database_session: db session
    :param user: user to use when querying system from DesignSafe
    :param system_id: str
    :return: project data

    """
    from geoapi.utils.external_apis import ApiUtils

    logger.debug(f"Getting project metadata for system:{system_id}")

    uuid = system_id[len("project-") :]
    client = ApiUtils(database_session, user, settings.DESIGNSAFE_URL)
    resp = client.get(f"/api/projects/v2/{uuid}/")
    resp.raise_for_status()

    project = resp.json()["baseProject"]["value"]
    return project


def get_designsafe_project_id(
    database_session, user: User, system_id: str
) -> str | None:
    """Get designsafe project id (i.e. PRJ-XXXX)

    If not a DS project or error occurs we return None
    """
    if not is_designsafe_project(system_id):
        logger.debug(f"System {system_id} is not a DesignSafe project, skipping")
        return None

    # Check cache first
    if system_id in DESIGNSAFE_PROJECT_ID_CACHE:
        return DESIGNSAFE_PROJECT_ID_CACHE[system_id]

    # Not in cache - fetch from DesignSafe API
    try:
        designsafe_project_data = get_designsafe_project_data(
            database_session=database_session, user=user, system_id=system_id
        )
        designsafe_project_id = designsafe_project_data["projectId"]

        # Cache it
        DESIGNSAFE_PROJECT_ID_CACHE[system_id] = designsafe_project_id

        logger.debug(
            f"Fetched and cached project_id for system {system_id}: {designsafe_project_id}"
        )
        return designsafe_project_id
    except Exception as e:
        logger.exception(
            f"Failed to fetch DesignSafe project_id for system {system_id}: {e}"
        )
        return None
