"""
Task to check if files from private DesignSafe projects have been published
and update their current_system/current_path accordingly.
"""

from datetime import datetime, timezone
from typing import Dict
import os

from sqlalchemy import and_, or_

from geoapi.celery_app import app
from geoapi.db import create_task_session
from geoapi.models import Project, Feature, User, TaskStatus, PointCloud
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

    # Build file index starting from root of project
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
        tuple of (is_published, system, path)
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


def fix_and_backfill(
    session,
    tapis_client,
    project: Project,
    asset: FeatureAsset,
    project_system: str,
    project_system_file_tree: Dict,
):
    """This method attempts to fix and backfill any information

    There are missing information that we can try to fix. These things have been fixed for
    newly created features, but we are trying to correct them for older features.
    They are:
      * (A) missing original_system                  -- only original_path was stored (original_system,
                                                    current_system, current_path came later) but we
                                                    might find the file in the system associated with
                                                    the map
      * (B) missing current_system, current_path    -- can baac with original_path and original_system
      * (C) original_path missing for point clouds   -- but can be derived from the point_cloud model
      * (E) features derived from geojson or shapefiles don't have file info; TODO in WG-600
      * (D) raster files (tile layers) missing current path and current system (TODO)

      This methods fixes these things except for (D) and (E)
    """
    logger.debug(f"Checking asset={asset.id} to see if we can fix anything")
    # (C) See if point cloud can be fixed (we do this first as results
    # might be used by B or A steps)
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
        # We can make assume that if the map project is connected to a
        # DS project, then it is possible that is the system where the data resides.
        # We check that system for the file and update original_system if there is a match.
        logger.debug(
            f"Missing original_system for asset={asset.id} so seeing if we see file on current DS project"
        )
        if file_exists(tapis_client, project.system_id, asset.original_path):
            logger.debug(
                f"Found file on current DS project so updating original_system to {project.system_id} "
            )
            asset.original_system = project.system_id

    # (B) Backfill current_system/current_path for legacy data
    if not asset.current_system and asset.original_system:
        logger.debug(
            f"Updated current_system for asset={asset.id} to {asset.original_system}"
        )
        asset.current_system = asset.original_system
    if not asset.current_path and asset.original_path:
        logger.debug(
            f"Updated current_path for asset={asset.id} to {asset.original_path} "
        )
        asset.current_path = asset.original_path

    logger.debug(f"Completed checking asset={asset.id}")


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

            tapis_client = TapisUtils(session, user)

            # Calculate the file tree of published DS project associated with this map project and place in a cache
            # that will hold it and then possibly from other systems/projects
            # (we assume most files will be from here, but they could be from other DS projects as well)
            published_file_tree_cache = {}
            if project.system_id:
                published_file_tree_cache[project.system_id] = (
                    get_file_tree_for_published_project(
                        session, user, project.system_id
                    )
                )

            # Check if any point clouds are missing original path
            has_point_cloud_missing_original_path = (
                session.query(FeatureAsset)
                .join(Feature, Feature.id == FeatureAsset.feature_id)
                .filter(
                    and_(
                        Feature.project_id == project_id,
                        FeatureAsset.asset_type == "point_cloud",
                        FeatureAsset.original_path.is_(None),
                    )
                )
                .first()
                is not None
            )

            unpublished_project_file_index = {}
            if has_point_cloud_missing_original_path and is_designsafe_project(
                project.system_id
            ):
                logger.info(
                    "Point cloud asset(s) are missing original_path so we gather file listing to attempt to fix that"
                )
                # Create a listing for current project in case we need to
                unpublished_project_file_index = build_file_index_from_tapis(
                    tapis_client, system_id=project.system_id, path="//"
                )
                logger.info(f"Indexed {len(unpublished_project_file_index)} files")

            # Process each asset
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
                    fix_and_backfill(
                        session=session,
                        tapis_client=tapis_client,
                        project=project,
                        asset=asset,
                        project_system=project.system_id,
                        project_system_file_tree=unpublished_project_file_index,
                    )

                    # Skip if already on a public system
                    if asset.current_system in PUBLIC_SYSTEMS:
                        asset.is_on_public_system = True
                        session.add(asset)
                    else:
                        if asset.current_system is None:
                            logger.warning(
                                f"We don't know the current system:"
                                f" asset={asset.id} asset_type={asset.asset_type}"
                                f" original_path={asset.original_path} original_system={asset.original_system}"
                                f" current_path={asset.current_path} current_system={asset.current_system} "
                            )

                        # TODO We should use https://www.designsafe-ci.org/api/publications/v2/PRJ-1234 endpoint to look
                        # at files (e.g fileObjs) but currently does not appear complete and and missing a previous-path attribute
                        if (
                            asset.current_system
                            and asset.current_system not in published_file_tree_cache
                        ):
                            # First time seeing this system - fetch and cache it
                            logger.info(
                                f"Discovering new system {asset.current_system}, building file tree"
                            )
                            published_file_tree_cache[asset.current_system] = (
                                get_file_tree_for_published_project(
                                    session, user, asset.current_system
                                )
                            )

                        published_project_file_tree = published_file_tree_cache.get(
                            asset.current_system, {}
                        )

                        # Check if file exists in published tree
                        exists, found_path = determine_if_exists_in_tree(
                            published_project_file_tree, asset.current_path
                        )

                        asset.is_on_public_system = exists

                        if exists and found_path:
                            asset.current_system = DESIGNSAFE_PUBLISHED_SYSTEM
                            asset.current_path = found_path

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
