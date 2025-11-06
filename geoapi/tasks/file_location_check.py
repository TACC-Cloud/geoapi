"""
Task to check if files from private DesignSafe projects have been published
and update their current_system/current_path accordingly.
"""

from datetime import datetime, timezone
from typing import Dict
import os

from sqlalchemy import and_

from geoapi.celery_app import app
from geoapi.db import create_task_session
from geoapi.models import Project, Feature, User, TaskStatus
from geoapi.models.feature import FeatureAsset
from geoapi.services.file_location_status import FileLocationStatusService
from geoapi.utils.external_apis import TapisUtils, get_session, TapisListingError
from geoapi.log import logger
from geoapi.tasks.utils import update_task_and_send_progress_update
from geoapi.settings import settings


DESIGNSAFE_PUBLISHED_SYSTEM = "designsafe.storage.published"
PUBLIC_SYSTEMS = [
    DESIGNSAFE_PUBLISHED_SYSTEM,
    "designsafe.storage.community",
]

BATCH_SIZE = 100  # Commit every 100 files


def extract_project_uuid(system_id: str) -> str | None:
    if system_id.startswith("project-"):
        return system_id.removeprefix("project-")
    return None


def is_designsafe_project(system_id: str) -> bool:
    return system_id.startswith("project-")


def build_file_index_from_tapis(
    client, system_id: str, path: str = "/"
) -> dict[str, list[str]]:
    """
    Recursively walk Tapis file system and build index.
    Returns dict where:
    - key = filename only
    - value = list of paths (without system prefix)
    """
    file_index = {}

    try:
        listing = client.listing(system_id, path)
    except TapisListingError:
        logger.exception(f"Unable to list {system_id}/{path}")
        return file_index

    for item in listing:
        if item.type == "dir" and not str(item.path).endswith(".Trash"):
            # Recursively get files from subdirectory
            sub_index = build_file_index_from_tapis(client, system_id, item.path)
            # Merge subdirectory results
            for filename, paths in sub_index.items():
                if filename not in file_index:
                    file_index[filename] = []
                file_index[filename].extend(paths)
        else:
            # It's a file - add to index (path only, no system)
            filename = os.path.basename(str(item.path))
            file_path = str(item.path).lstrip("/")  # Just the path

            if filename not in file_index:
                file_index[filename] = []
            file_index[filename].append(file_path)

    return file_index


def get_project_id(user, system_id):
    """Get project id (PRJ-123) for system attached to system_id"""
    designsafe_uuid = extract_project_uuid(system_id)

    client = get_session(user)
    response = client.get(
        settings.DESIGNSAFE_URL + f"/api/projects/v2/{designsafe_uuid}/"
    )
    response.raise_for_status()
    return response.json()["baseProject"]["value"]["projectId"]


def get_file_tree_for_published_project(
    session, user, system_id
) -> dict[str, list[str]] | None:
    """Get file tree for published ds project given a geoapi map project

    If `system_id` is not a DS project's system (i.e. My Data) then return None

    """

    if is_designsafe_project(system_id) is False:
        # it is not a DS project
        logger.info(f"Issue with system:{system_id}. Not a typical project")
        return None

    designsafe_prj = get_project_id(user, system_id)

    tapis_client = TapisUtils(session, user)

    # Build file index starting from root of project
    file_index = build_file_index_from_tapis(
        tapis_client, DESIGNSAFE_PUBLISHED_SYSTEM, f"/published-data/{designsafe_prj}/"
    )

    logger.info(
        f"Built file tree for {system_id}: " f"{len(file_index)} unique filenames"
    )

    return file_index


def determine_if_published(
    file_tree: Dict | None, asset: FeatureAsset
) -> tuple[bool, str | None, str | None]:
    """
    Check if asset's file exists in the published file tree.

    Returns:
        tuple of (is_published, system, path)
    """
    if file_tree is None or not asset.current_path:
        return (False, None, None)

    filename = os.path.basename(asset.current_path)

    if filename in file_tree:
        published_paths = file_tree[filename]

        if len(published_paths) > 1:
            logger.info(
                f"Multiple matches found for asset {asset.id} file '{filename}': "
                f"{published_paths}"
            )

        # Use first match - path only (no system)
        path = "/" + published_paths[0].lstrip("/")

        logger.debug(
            f"Asset {asset.id} found in published system: "
            f"{DESIGNSAFE_PUBLISHED_SYSTEM}{path}"
        )

        return (True, DESIGNSAFE_PUBLISHED_SYSTEM, path)

    return (False, None, None)


@app.task(queue="default")
def check_and_update_file_locations(user_id: int, project_id: int):
    """
    Check all feature assets in a project and update where they are located (i.e. new published
    location) and then check if they are located tapis system that is publicly accessible

    Updates:
    - FeatureAsset.current_system and current_path if file found in public system
    - FeatureAsset.is_on_public_system based on current_system
    - FeatureAsset.last_public_system_check timestamp
    - FileLocationCheck record with new info
    """
    logger.info(f"Starting file location check for project:{project_id} user:{user_id}")

    with create_task_session() as session:
        user = None
        file_location_check = None
        failed_assets = []

        try:
            user = session.get(User, user_id)
            project = session.get(Project, project_id)
            file_location_check = FileLocationStatusService.get(
                session, project_id=project_id
            )

            if not user or not project or not file_location_check:
                logger.error(
                    f"Missing required entities: user={user_id}, project={project_id}"
                )
                return

            # Get all feature assets for this project
            # NOTE: This only includes Features that have FeatureAssets (photos, videos, etc.)
            # Features without assets (geometry-only) are excluded - they have no files to check.
            # TODO WG-600: Consider how to handle "source" FeatureAssets (shapefiles, etc.)
            #              that represent the file that created the feature rather than
            #              assets belonging to the feature. Currently these are checked if they
            #              have original_system/original_path, but may need special handling.
            feature_assets = (
                session.query(FeatureAsset)
                .join(Feature, Feature.id == FeatureAsset.feature_id)
                .filter(
                    and_(
                        Feature.project_id == project_id,
                        FeatureAsset.original_path.isnot(None),
                    )
                )
                .all()
            )

            total_checked = len(feature_assets)

            # Set total files count
            file_location_check.total_files = total_checked
            session.commit()

            logger.info(
                f"Starting check for project {project_id}: {total_checked} assets to check"
            )

            update_task_and_send_progress_update(
                session,
                user,
                task_id=file_location_check.task.id,
                latest_message=f"Checking {total_checked} files for public availability",
            )

            # Calculate the file tree of DS project associated with this map project and place in a cache
            # that will hold it and then possibly from other systems/projects
            # (we assume most files will be from here, but they could be from other DS projects as well)
            file_tree_cache = {}
            if project.system_id:
                file_tree_cache[project.system_id] = (
                    get_file_tree_for_published_project(
                        session, user, project.system_id
                    )
                )

            # Process each asset
            for i, asset in enumerate(feature_assets):
                try:
                    # Update timestamp
                    asset.last_public_system_check = datetime.now(timezone.utc)

                    # TODO If missing, original_path we can derive from some like point cloud (by
                    # looking at point cloud matched with this feature and then looking at files_info.

                    # Backfill current_system/current_path for legacy data
                    if not asset.current_system:
                        asset.current_system = asset.original_system
                    if not asset.current_path:
                        asset.current_path = asset.original_path

                    # Skip if already on a public system
                    if asset.current_system in PUBLIC_SYSTEMS:
                        asset.is_on_public_system = True
                        session.add(asset)
                    else:
                        current_system = asset.current_system
                        if not current_system:
                            # some legacy data is missing original_system (and then current_system)
                            # We don't update original_system as to be accurate about what was
                            # recorded at the time of feature creation.
                            #
                            # But we can make assume that if the map project is connected to a
                            # DS project, then it is possible this is the system where the data
                            # resides and so we can search there for a match.
                            #
                            # Note: we wait until we find the file in the published project before
                            # setting `asset.current_system` so this is why we are using a variable
                            # (`current_system`) instead immediately setting `asset.current_system``
                            current_system = project.system_id

                        # TODO We should use https://www.designsafe-ci.org/api/publications/v2/PRJ-1234 endpoint to look
                        # at files (e.g fileObjs) but currently does not appear complete and and missing a previous-path attribute

                        if current_system not in file_tree_cache:
                            # First time seeing this system - fetch and cache it
                            logger.info(
                                f"Discovering new system {current_system}, building file tree"
                            )
                            file_tree_cache[current_system] = (
                                get_file_tree_for_published_project(
                                    session, user, current_system
                                )
                            )

                        file_tree = file_tree_cache.get(current_system)

                        # Check if file exists in published tree
                        is_published, new_system, new_path = determine_if_published(
                            file_tree, asset
                        )

                        asset.is_on_public_system = is_published

                        if is_published and new_system and new_path:
                            asset.current_system = new_system
                            asset.current_path = new_path

                        session.add(asset)

                    # Commit and clear cache in batches
                    if (i + 1) % BATCH_SIZE == 0:
                        session.commit()
                        session.expire_all()

                        # Update counts
                        file_location_check.files_checked = i + 1 - len(failed_assets)
                        file_location_check.files_failed = len(failed_assets)
                        session.commit()

                        logger.info(
                            f"Batch: {i + 1}/{total_checked} processed, {len(failed_assets)} errors"
                        )

                        update_task_and_send_progress_update(
                            session,
                            user,
                            task_id=file_location_check.task.id,
                            latest_message=f"Processed {i + 1}/{total_checked} files ({len(failed_assets)} errors)",
                        )

                except Exception as e:
                    error_msg = str(e)[:100]
                    logger.exception(
                        f"Error checking asset {asset.id} ({asset.original_path}): {e}"
                    )

                    failed_assets.append(
                        {
                            "asset_id": asset.id,
                            "path": asset.original_path or "unknown",
                            "error": error_msg,
                        }
                    )

                    session.rollback()
                    continue

            # Final commit for remaining items
            session.commit()

            # Update final counts
            file_location_check.completed_at = datetime.now(timezone.utc)
            file_location_check.files_checked = total_checked - len(failed_assets)
            file_location_check.files_failed = len(failed_assets)
            session.add(file_location_check)
            session.commit()

            if failed_assets:
                logger.warning(
                    f"File location check completed with {len(failed_assets)} failures for project {project_id}. "
                    f"Failed assets: {failed_assets}"
                )

            if failed_assets:
                final_message = (
                    f"Checked {total_checked} files: {file_location_check.files_checked} successful,"
                    f" {len(failed_assets)} failed"
                )
            else:
                final_message = f"Successfully checked all {total_checked} files"

            logger.info(f"Check completed for project {project_id}: {final_message}")

            update_task_and_send_progress_update(
                session,
                user,
                task_id=file_location_check.task.id,
                status=TaskStatus.COMPLETED,
                latest_message=final_message,
            )

        except Exception as e:
            logger.exception(f"Check failed for project {project_id}: {e}")

            # Mark task and check as FAILED
            try:
                if file_location_check:
                    file_location_check.completed_at = datetime.now(timezone.utc)
                    # Keep existing counts if we got that far
                    session.add(file_location_check)

                if file_location_check and file_location_check.task and user:
                    update_task_and_send_progress_update(
                        session,
                        user,
                        task_id=file_location_check.task.id,
                        status=TaskStatus.FAILED,
                        latest_message=f"Check failed: {str(e)[:200]}",
                    )

                session.commit()
            except Exception as cleanup_error:
                logger.exception(f"Failed to mark task as failed: {cleanup_error}")
                session.rollback()

                # Re-raise to mark Celery task as failed as we can't even mark our internal
                # task as failed
                raise
