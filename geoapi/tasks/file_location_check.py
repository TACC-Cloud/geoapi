"""
Task to check if files from private DesignSafe projects have been published
and update their current_system/current_path accordingly.
"""

from datetime import datetime, timezone
from typing import Dict, Union
import os

from sqlalchemy import and_, or_

from geoapi.celery_app import app
from geoapi.db import create_task_session
from geoapi.services.tile_server import TileService
from geoapi.models import Project, Feature, User, TaskStatus, PointCloud, TileServer
from geoapi.models.feature import FeatureAsset
from geoapi.services.file_location_status import FileLocationStatusService
from geoapi.utils.external_apis import TapisUtils, get_session, TapisListingError
from geoapi.log import logger
from geoapi.tasks.utils import update_task_and_send_progress_update
from geoapi.settings import settings
from geoapi.custom.designsafe.utils import (
    get_designsafe_project_id,
    extract_project_uuid,
    is_designsafe_project,
)


DESIGNSAFE_PUBLISHED_SYSTEM = "designsafe.storage.published"
PUBLIC_SYSTEMS = [
    DESIGNSAFE_PUBLISHED_SYSTEM,
    "designsafe.storage.community",
]
BATCH_SIZE = 500  # Commit every 500 items


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
        # TODO handle 404 better as we might just be missing published project
        logger.exception(
            f"Unable to list {system_id}/{path}.  If 404, Project might not be published yet"
        )
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

    # Calculate the file tree of published DS project associated with this map project and place in a cache
    # that will hold it and then possibly from other systems/projects
    # (we assume most files will be from here, but they could be from other DS projects as well)
    file_index = build_file_index_from_tapis(
        tapis_client, DESIGNSAFE_PUBLISHED_SYSTEM, f"/published-data/{designsafe_prj}/"
    )

    logger.info(
        f"Built file tree for {system_id}: " f"{len(file_index)} unique filenames"
    )

    return file_index


def file_exists(client, system_id: str, path: str) -> bool:
    """Check if file exists by trying to list it directly"""
    try:
        listing = client.listing(system_id, path)
        # If listing succeeds, file exists
        return len(listing) > 0
    except TapisListingError:
        return False


def determine_if_exists_in_tree(
    file_tree: Dict | None, current_file_path: str
) -> tuple[bool, str | None]:
    """
    Check if asset's file exists in the file tree.

    Returns:
        tuple of (is_published, path)
    """
    if file_tree is None or not current_file_path:
        return (False, None)

    filename = os.path.basename(current_file_path)

    if filename in file_tree:
        published_paths = file_tree[filename]

        if len(published_paths) > 1:
            logger.info(
                f"Multiple matches found for asset file '{current_file_path}': "
                f"{published_paths}"
            )

        # Use first match - path only (no system)
        path = "/" + published_paths[0].lstrip("/")

        logger.debug(f"Asset '{current_file_path}' found in system at: {path}")

        return (True, path)

    return (False, None)


def get_filename_from_point_cloud_asset(session, asset: FeatureAsset) -> str | None:
    """
    Get the point cloud filename from a point cloud asset by querying the associated
    PointCloud and extracting the first .laz file from files_info.

    Returns the name of the first .laz file found, or None if no point cloud
    or .laz file exists.

    Note: If there are multiple .laz files, only the first one is returned.
    """
    # Query for the PointCloud associated with this feature
    point_cloud = (
        session.query(PointCloud).filter_by(feature_id=asset.feature_id).first()
    )

    # Return None if no point cloud exists or files_info is empty/None
    if not point_cloud or not point_cloud.files_info:
        return None

    # Look for the first .laz file in files_info
    # Note: Taking the first .laz file found; multiple files are not handled
    for file_info in point_cloud.files_info:
        name = file_info.get("name", None)
        return name
    return None


def backfill_current_location(item: Union[FeatureAsset, TileServer]) -> None:
    """
    Backfill current_system/current_path from original_* if missing.
    Works for both FeatureAsset and TileServer.
    """
    if not item.current_system and item.original_system:
        logger.debug(
            f"Updated current_system for {type(item).__name__}={item.id} to {item.original_system}"
        )
        item.current_system = item.original_system

    if not item.current_path and item.original_path:
        logger.debug(
            f"Updated current_path for {type(item).__name__}={item.id} to {item.original_path}"
        )
        item.current_path = item.original_path


def fix_and_backfill_feature_asset(
    session,
    tapis_client,
    project: Project,
    asset: FeatureAsset,
    project_system: str,
    project_system_file_tree: Dict,
):
    """
    Fix and backfill FeatureAsset-specific information.

    Handles:
    - (A) missing original_system
    - (B) missing current_system, current_path
    - (C) original_path missing for point clouds
    """
    logger.debug(f"Checking asset={asset.id} to see if we can fix anything")

    # (C) See if point cloud can be fixed (we do this first as results might be used by B or A steps)
    if asset.original_path is None and asset.asset_type == "point_cloud":
        file_name = get_filename_from_point_cloud_asset(session, asset)
        logger.info(
            f"Point cloud asset missing original_path. Will try to fix by looking for {file_name} in systems files"
        )
        exists, found_path = determine_if_exists_in_tree(
            project_system_file_tree, file_name
        )
        if exists:
            logger.info(
                f"Found path for point cloud asset={asset.id} and fixing original_path to {found_path}"
            )
            asset.original_path = found_path
            asset.original_system = project_system
        else:
            logger.info("Did not find a matching path")

    # (A) some legacy data is missing original_system
    if not asset.original_system:
        logger.debug(
            f"Missing original_system for asset={asset.id} so seeing if we see file on current DS project"
        )
        if file_exists(tapis_client, project.system_id, asset.original_path):
            logger.debug(
                f"Found file on current DS project so updating original_system to {project.system_id}"
            )
            asset.original_system = project.system_id

    # (B) Backfill current_system/current_path for legacy data
    backfill_current_location(asset)

    logger.debug(f"Completed checking asset={asset.id}")


def check_and_update_designsafe_project_id(
    item: Union[FeatureAsset, TileServer],
    session,
    user,
) -> None:
    """
    Check and update the designsafe_project_id for an item based on its current_system.
    Uses module-level caching to minimize API calls to DesignSafe.

    Args:
        item: FeatureAsset or TileServer to update
        session: Database session
        user: User for API calls
    """

    if item.designsafe_project_id:
        logger.debug("Nothing to do as item has designsafe_project_id")
        return

    # Check if we can derive PRJ from published projects path
    if (
        item.original_system == "designsafe.storage.published"
        and item.original_path
        and item.original_path.startswith("/published-data/PRJ-")
    ):
        parts = item.original_path.split("/")
        item.designsafe_project_id = parts[2]  # PRJ-XXXX
        return

    # Determine which system to use
    system_to_check = item.original_system or item.current_system

    if not system_to_check:
        logger.debug(f"No system to check for {type(item).__name__}={item.id}")
        return

    if not is_designsafe_project(system_to_check):
        logger.debug(f"System {system_to_check} is not a DesignSafe project, skipping")
        return

    designsafe_project_id = get_designsafe_project_id(session, user, system_to_check)
    if designsafe_project_id:
        logger.debug(f"Setting item's designsafe_project_id to {designsafe_project_id}")
        item.designsafe_project_id = designsafe_project_id


def check_and_update_public_system(
    item: Union[FeatureAsset, TileServer],
    published_file_tree_cache: Dict,
    session,
    user,
) -> None:
    """
    Check if item is on a public system and update location if found in published tree.
    Works for both FeatureAsset and TileServer.
    """
    item_type = type(item).__name__
    item_id = item.id

    # Skip if already on a public system
    if item.current_system in PUBLIC_SYSTEMS:
        item.is_on_public_system = True
        return

    if item.current_system is None:
        logger.warning(
            f"We don't know the current system: {item_type}={item_id}"
            f" original_path={item.original_path} original_system={item.original_system}"
            f" current_path={item.current_path} current_system={item.current_system}"
        )
        return

    # Cache published file tree for this system if not already cached
    if item.current_system not in published_file_tree_cache:
        logger.info(f"Discovering new system {item.current_system}, building file tree")
        published_file_tree_cache[item.current_system] = (
            get_file_tree_for_published_project(session, user, item.current_system)
        )

    published_project_file_tree = published_file_tree_cache.get(item.current_system, {})

    # Check if file exists in published tree
    exists, found_path = determine_if_exists_in_tree(
        published_project_file_tree, item.current_path
    )

    item.is_on_public_system = exists

    if exists and found_path:
        item.current_system = DESIGNSAFE_PUBLISHED_SYSTEM
        item.current_path = found_path


@app.task(queue="default")
def check_and_update_file_locations(user_id: int, project_id: int):
    """
    Check all feature assets and tile servers in a project and update where they are located
    (i.e. new published location) and then check if they are on a publicly accessible system.

    Updates:
    - FeatureAsset/TileServer: current_system, current_path, is_on_public_system, last_public_system_check
    - FileLocationCheck record with check metadata
    """
    logger.info(f"Starting file location check for project:{project_id} user:{user_id}")

    with create_task_session() as session:
        user = None
        file_location_check = None
        failed_items = []

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
            #
            # * Features without assets (geometry-only) are excluded - they have no files to check. (WG-600)
            # * Point cloud assets without original_path are included for backfilling from PointCloud.files_info
            #
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
                        or_(
                            FeatureAsset.original_path.isnot(None),
                            FeatureAsset.asset_type == "point_cloud",
                        ),
                    )
                )
                .all()
            )

            # Get all internal tile servers for this project
            # Only check internal tile servers (served by geoapi)
            # External tile servers are using external URLs and don't need checking
            tile_servers = TileService.getTileServers(
                session, projectId=project_id, internal=True
            )

            total_checked = len(feature_assets) + len(tile_servers)

            # Set total files count
            file_location_check.total_files = total_checked
            session.commit()

            logger.info(
                f"Starting check for project {project_id}: "
                f"{len(feature_assets)} feature assets + {len(tile_servers)} tile servers = {total_checked} items to check"
            )

            update_task_and_send_progress_update(
                session,
                user,
                task_id=file_location_check.task.id,
                latest_message=f"Checking {total_checked} files for public availability",
            )

            tapis_client = TapisUtils(session, user)

            # Build published file tree cache
            published_file_tree_cache = {}
            if project.system_id:
                published_file_tree_cache[project.system_id] = (
                    get_file_tree_for_published_project(
                        session, user, project.system_id
                    )
                )

            # Check if any point clouds need unpublished project file index
            has_point_cloud_missing_original_path = any(
                asset.original_path is None and asset.asset_type == "point_cloud"
                for asset in feature_assets
            )

            # Create a listing for current project in case we need to use it
            unpublished_project_file_index = {}
            if has_point_cloud_missing_original_path and is_designsafe_project(
                project.system_id
            ):
                logger.info(
                    "Point cloud asset(s) are missing original_path so we gather file listing to attempt to fix that"
                )
                unpublished_project_file_index = build_file_index_from_tapis(
                    tapis_client, system_id=project.system_id, path="//"
                )
                logger.info(f"Indexed {len(unpublished_project_file_index)} files")

            if not project.designsafe_project_id:
                designsafe_project_id = get_designsafe_project_id(
                    database_session=session, user=user, system_id=project.system_id
                )
                if designsafe_project_id:
                    project.designsafe_project_id = designsafe_project_id
                    session.add(project)

            # Process each feature asset
            for i, asset in enumerate(feature_assets):
                try:
                    # Update timestamp
                    asset.last_public_system_check = datetime.now(timezone.utc)

                    logger.debug(
                        f"Processing asset={asset.id} asset_type={asset.asset_type}"
                        f" original_path={asset.original_path} original_system={asset.original_system}"
                        f" current_path={asset.current_path} current_system={asset.current_system}"
                    )

                    # Fix attributes of any assets missing info as they were created in the past
                    fix_and_backfill_feature_asset(
                        session=session,
                        tapis_client=tapis_client,
                        project=project,
                        asset=asset,
                        project_system=project.system_id,
                        project_system_file_tree=unpublished_project_file_index,
                    )

                    # Check and update DesignSafe project ID
                    check_and_update_designsafe_project_id(
                        session=session, item=asset, user=user
                    )

                    # Check and update public system status
                    check_and_update_public_system(
                        asset, published_file_tree_cache, session, user
                    )

                    session.add(asset)

                    # Commit in large batches for memory management (rare 5000+ item cases)
                    if (i + 1) % BATCH_SIZE == 0:
                        session.commit()
                        session.expire_all()
                        logger.info(
                            f"Batch: {i + 1}/{total_checked} processed, {len(failed_items)} errors"
                        )

                except Exception as e:
                    error_msg = str(e)[:100]
                    logger.exception(
                        f"Error checking asset {asset.id} ({asset.original_path}): {e}"
                    )

                    failed_items.append(
                        {
                            "type": "feature_asset",
                            "id": asset.id,
                            "path": asset.original_path or "unknown",
                            "error": error_msg,
                        }
                    )

                    session.rollback()
                    continue

            # Process each tile server
            for i, tile_server in enumerate(tile_servers, start=len(feature_assets)):
                try:
                    # Update timestamp
                    tile_server.last_public_system_check = datetime.now(timezone.utc)

                    logger.debug(
                        f"Processing tile_server={tile_server.id} name={tile_server.name}"
                        f" original_path={tile_server.original_path} original_system={tile_server.original_system}"
                        f" current_path={tile_server.current_path} current_system={tile_server.current_system}"
                    )

                    # Backfill current_system/current_path if missing
                    backfill_current_location(tile_server)

                    # Check and update public system status
                    check_and_update_public_system(
                        tile_server, published_file_tree_cache, session, user
                    )

                    session.add(tile_server)

                    # Commit in large batches
                    if (i + 1) % BATCH_SIZE == 0:
                        session.commit()
                        session.expire_all()
                        logger.info(
                            f"Batch: {i + 1}/{total_checked} processed, {len(failed_items)} errors"
                        )

                except Exception as e:
                    error_msg = str(e)[:100]
                    logger.exception(
                        f"Error checking tile_server {tile_server.id} ({tile_server.name}): {e}"
                    )

                    failed_items.append(
                        {
                            "type": "tile_server",
                            "id": tile_server.id,
                            "name": tile_server.name,
                            "path": tile_server.original_path or "unknown",
                            "error": error_msg,
                        }
                    )

                    session.rollback()
                    continue

            # Final commit for remaining items
            session.commit()

            # Update final counts
            file_location_check.completed_at = datetime.now(timezone.utc)
            file_location_check.files_checked = total_checked - len(failed_items)
            file_location_check.files_failed = len(failed_items)
            session.add(file_location_check)
            session.commit()

            if failed_items:
                logger.warning(
                    f"File location check completed with {len(failed_items)} failures for project {project_id}. "
                    f"Failed items: {failed_items}"
                )

            final_message = (
                f"Checked {total_checked} files: {file_location_check.files_checked} successful, {len(failed_items)} failed"
                if failed_items
                else f"Successfully checked all {total_checked} files"
            )

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
                # task as faile
                raise
