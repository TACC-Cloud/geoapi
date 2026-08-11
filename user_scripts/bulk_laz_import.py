import sys

# Check for required dependencies
missing_packages = []

try:
    from tapipy.tapis import Tapis
except ImportError:
    missing_packages.append("tapipy")

try:
    import requests
except ImportError:
    missing_packages.append("requests")

if missing_packages:
    print()
    print("  Error: Missing required packages.")
    print()
    print("  Install with:")
    print(f"    pip install {' '.join(missing_packages)}")
    print()
    print("  Then re-run this script.")
    print()
    sys.exit(1)

import getpass
import logging
import re
import json
import os
import time
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Global clients
t = None
jwt = None

# Configuration
HAZMAPPER_BACKEND = "https://hazmapper.tacc.utexas.edu/geoapi"
DESIGNSAFE_API = "https://www.designsafe-ci.org/api/projects/v2"
CONFIG_FILE = os.path.expanduser("~/.laz_processor_config.json")
DELAY_BETWEEN_FILES = 0.5  # seconds between file submissions

# Terminal states for point cloud tasks
TERMINAL_STATES = {"FINISHED", "FAILED", "CANCELLED", "ERROR"}
IN_PROGRESS_STATES = {"PENDING", "QUEUED", "RUNNING", "PROCESSING"}


def clear_screen():
    print("\033[H\033[J", end="")


def print_header(title):
    width = 80
    print("=" * width)
    print(f"{title:^{width}}")
    print("=" * width)


def print_divider():
    print("-" * 80)


def format_size(size_bytes):
    """Format bytes to human readable."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"


def format_datetime(dt_string):
    """Format ISO datetime to readable format."""
    if not dt_string:
        return "N/A"
    try:
        dt = datetime.fromisoformat(dt_string.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return dt_string[:16] if len(dt_string) > 16 else dt_string


def get_hazmapper_feature_url(hazmapper_uuid, feature_id):
    """Generate URL to view a specific feature in Hazmapper."""
    return f"https://hazmapper.tacc.utexas.edu/hazmapper/project/{hazmapper_uuid}?selectedFeature={feature_id}"


def load_saved_config():
    """Load saved configuration from file."""
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None


def save_config(config):
    """Save configuration to file (excluding sensitive data)."""
    # Only save non-sensitive fields
    save_data = {
        "username": config.get("username", ""),
        "hazmapper_url": config.get("hazmapper_url", ""),
        "hazmapper_uuid": config.get("hazmapper_uuid", ""),
        "hazmapper_name": config.get("hazmapper_name", ""),
        "prj_number": config.get("prj_number", ""),
        "project_title": config.get("project_title", ""),
        "paths": config.get("paths", []),
    }
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(save_data, f, indent=2)
    except Exception as e:
        logging.warning(f"Could not save config: {e}")


# =============================================================================
# CONFIGURATION & VALIDATION
# =============================================================================


def get_credentials(saved_config=None):
    """Get TACC credentials."""
    clear_screen()
    print_header("LAZ Point Cloud Processor - Authentication")
    print()

    saved_username = saved_config.get("username", "") if saved_config else ""

    if saved_username:
        print(f"  Saved username: {saved_username}")
        use_saved = input("  Use saved username? [Y/n]: ").strip().lower()
        if use_saved != "n":
            username = saved_username
        else:
            username = input("  Enter your TACC username: ").strip()
    else:
        username = input("  Enter your TACC username: ").strip()

    password = getpass.getpass("  Enter your TACC password: ")
    return username, password


def authenticate(username, password):
    """Authenticate with Tapis."""
    global t, jwt
    print()
    print("  Authenticating with Tapis...")

    t = Tapis(
        base_url="https://designsafe.tapis.io", username=username, password=password
    )
    t.get_tokens()
    jwt = t.access_token.access_token
    print("  ✓ Authentication successful!")
    return True


def parse_hazmapper_url(url):
    """Extract UUID from Hazmapper URL."""
    # Pattern: https://hazmapper.tacc.utexas.edu/hazmapper/project/<uuid>
    # or: https://hazmapper.tacc.utexas.edu/hazmapper/project-public/<uuid>
    pattern = (
        r"hazmapper\.tacc\.utexas\.edu/hazmapper/project(?:-public)?/([a-f0-9-]{36})"
    )
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None


def get_hazmapper_project_info(hazmapper_uuid):
    """Get Hazmapper project info from UUID."""
    try:
        response = requests.get(
            f"{HAZMAPPER_BACKEND}/projects/?uuid={hazmapper_uuid}",
            headers={"X-Tapis-Token": jwt},
        )
        response.raise_for_status()
        projects = response.json()
        if projects and len(projects) > 0:
            return projects[0]
        return None
    except Exception as e:
        logging.error(f"Failed to get Hazmapper project info: {e}")
        return None


def get_designsafe_project_info(prj_number):
    """Get DesignSafe project info from PRJ number."""
    try:
        # Strip 'PRJ-' prefix if present
        prj_id = prj_number.upper().replace("PRJ-", "")

        response = requests.get(
            f"{DESIGNSAFE_API}/PRJ-{prj_id}/", headers={"X-Tapis-Token": jwt}
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Failed to get DesignSafe project info: {e}")
        return None


def validate_path_exists(system_id, path):
    """Check if path exists on the system."""
    try:
        files = t.files.listFiles(systemId=system_id, path=path, limit=1)
        return True
    except Exception as e:
        return False


def get_config_interactive():
    """Interactive configuration with validation."""
    config = {}
    saved_config = load_saved_config()

    # Get credentials first
    username, password = get_credentials(saved_config)
    if not authenticate(username, password):
        return None

    config["username"] = username

    # Check if we have saved config and offer to reuse
    if (
        saved_config
        and saved_config.get("hazmapper_uuid")
        and saved_config.get("prj_number")
    ):
        print()
        print_divider()
        print("  SAVED CONFIGURATION FOUND")
        print_divider()
        print(f"  Map:     {saved_config.get('hazmapper_name', 'N/A')}")
        print(
            f"  Project: {saved_config.get('prj_number', 'N/A')} - {saved_config.get('project_title', 'N/A')[:40]}"
        )
        print(f"  Paths:   {', '.join(saved_config.get('paths', [])[:2])}")
        print()
        use_saved = input("  Use saved configuration? [Y/n]: ").strip().lower()

        if use_saved != "n":
            # Validate saved config still works
            print()
            print("  Validating saved configuration...")

            hazmapper_info = get_hazmapper_project_info(saved_config["hazmapper_uuid"])
            if not hazmapper_info:
                print(
                    "  ✗ Saved Hazmapper map no longer accessible. Please reconfigure."
                )
                input("  Press Enter to continue...")
            else:
                ds_info = get_designsafe_project_info(saved_config["prj_number"])
                if not ds_info:
                    print(
                        "  ✗ Saved DesignSafe project no longer accessible. Please reconfigure."
                    )
                    input("  Press Enter to continue...")
                else:
                    # Extract fresh data
                    base_project = ds_info.get("baseProject", {})
                    project_uuid = base_project.get("uuid")

                    config["hazmapper_url"] = saved_config.get("hazmapper_url", "")
                    config["hazmapper_uuid"] = saved_config["hazmapper_uuid"]
                    config["hazmapper_project_id"] = hazmapper_info["id"]
                    config["hazmapper_name"] = hazmapper_info["name"]
                    config["hazmapper_system_id"] = hazmapper_info.get("system_id")
                    config["system_id"] = f"project-{project_uuid}"
                    config["project_title"] = base_project.get("value", {}).get(
                        "title", "Unknown"
                    )
                    config["prj_number"] = saved_config["prj_number"]
                    config["paths"] = saved_config.get("paths", [])

                    print(f"  ✓ Configuration validated!")

                    # Save updated config
                    save_config(config)
                    return config

    input("\n  Press Enter to continue to configuration...")

    # =========================
    # HAZMAPPER CONFIGURATION
    # =========================
    clear_screen()
    print_header("Hazmapper Map Configuration")
    print()
    print("  Enter the Hazmapper map URL where point clouds will be added.")
    print(
        "  Example: https://hazmapper.tacc.utexas.edu/hazmapper/project/efdccc0e-c522-4f21-a739-892399d853c3"
    )
    print()

    while True:
        hazmapper_url = input("  Hazmapper URL: ").strip()
        hazmapper_uuid = parse_hazmapper_url(hazmapper_url)

        if not hazmapper_uuid:
            print("  ✗ Could not parse UUID from URL. Please check the format.")
            continue

        print(f"  → Extracted UUID: {hazmapper_uuid}")
        print("  → Fetching Hazmapper project info...")

        hazmapper_info = get_hazmapper_project_info(hazmapper_uuid)
        if not hazmapper_info:
            print("  ✗ Could not find Hazmapper project. Check the URL and try again.")
            continue

        print(f"  ✓ Found map: {hazmapper_info['name']}")
        print(f"    ID: {hazmapper_info['id']}")
        print(f"    System: {hazmapper_info.get('system_id', 'N/A')}")

        config["hazmapper_url"] = hazmapper_url
        config["hazmapper_uuid"] = hazmapper_uuid
        config["hazmapper_project_id"] = hazmapper_info["id"]
        config["hazmapper_name"] = hazmapper_info["name"]
        config["hazmapper_system_id"] = hazmapper_info.get("system_id")
        break

    input("\n  Press Enter to continue...")

    # =========================
    # DESIGNSAFE PROJECT CONFIG
    # =========================
    clear_screen()
    print_header("DesignSafe Project Configuration")
    print()
    print("  Enter the DesignSafe project number containing the LAZ files.")
    print("  Example: PRJ-5815")
    print()

    while True:
        prj_number = input("  Project number (e.g., PRJ-5815): ").strip()

        print("  → Fetching DesignSafe project info...")
        ds_info = get_designsafe_project_info(prj_number)

        if not ds_info:
            print(
                "  ✗ Could not find DesignSafe project. Check the number and try again."
            )
            continue

        # Extract UUID from response
        base_project = ds_info.get("baseProject", {})
        project_uuid = base_project.get("uuid")
        project_title = base_project.get("value", {}).get("title", "Unknown")

        if not project_uuid:
            print("  ✗ Could not extract project UUID.")
            continue

        derived_system_id = f"project-{project_uuid}"

        print(f"  ✓ Found project: {project_title}")
        print(f"    UUID: {project_uuid}")
        print(f"    Derived System ID: {derived_system_id}")

        # Validate system IDs match (if Hazmapper has one)
        if config.get("hazmapper_system_id"):
            if config["hazmapper_system_id"] == derived_system_id:
                print(f"  ✓ System ID matches Hazmapper map!")
            else:
                print(f"  ⚠ WARNING: System ID mismatch!")
                print(f"    Hazmapper system: {config['hazmapper_system_id']}")
                print(f"    Derived system:   {derived_system_id}")
                confirm = input("  Continue anyway? [y/N]: ").strip().lower()
                if confirm != "y":
                    continue

        config["system_id"] = derived_system_id
        config["project_title"] = project_title
        config["prj_number"] = prj_number.upper()
        break

    input("\n  Press Enter to continue...")

    # =========================
    # PATH CONFIGURATION
    # =========================
    clear_screen()
    print_header("Source Path Configuration")
    print()
    print(f"  Project: {config['project_title']}")
    print(f"  System:  {config['system_id']}")
    print()
    print("  Enter the path(s) containing LAZ files.")
    print("  For multiple paths, separate with commas.")
    print(
        "  Example: /3_Deliverables/Eaton_Sept2025/PointClouds/Eaton_3Dmodel_500mTiles"
    )
    print()

    while True:
        paths_input = input("  Path(s): ").strip()
        paths = [p.strip() for p in paths_input.split(",")]

        print()
        valid_paths = []
        for path in paths:
            print(f"  → Validating: {path}")
            if validate_path_exists(config["system_id"], path):
                print(f"    ✓ Path exists")
                valid_paths.append(path)
            else:
                print(f"    ✗ Path not found!")

        if not valid_paths:
            print("\n  No valid paths found. Please try again.")
            continue

        if len(valid_paths) < len(paths):
            print(f"\n  Found {len(valid_paths)} of {len(paths)} paths.")
            confirm = input("  Continue with valid paths only? [Y/n]: ").strip().lower()
            if confirm == "n":
                continue

        config["paths"] = valid_paths
        break

    # Save config for next time
    save_config(config)

    return config


# =============================================================================
# DATA RETRIEVAL
# =============================================================================


def get_laz_files(system_id, paths):
    """Fetch all .laz files from specified paths."""
    all_laz_files = []

    for directory_path in paths:
        print(f"  Scanning: {directory_path}")
        laz_files = []
        offset = 0
        file_limit = 1000

        while True:
            files = t.files.listFiles(
                systemId=system_id, path=directory_path, limit=file_limit, offset=offset
            )
            laz_files.extend([file for file in files if file.path.endswith(".laz")])

            if len(files) < file_limit:
                break
            offset += file_limit

        print(f"    Found {len(laz_files)} .laz files")
        all_laz_files.extend(laz_files)

    # Sort by name
    laz_files_sorted = sorted(all_laz_files, key=lambda file: file.name)
    return laz_files_sorted


def get_point_cloud_status(hazmapper_project_id, laz_files):
    """
    Get detailed status of all point clouds.
    Returns: (completed, errors, pending, point_cloud_map)
    """
    response = requests.get(
        f"{HAZMAPPER_BACKEND}/projects/{hazmapper_project_id}/point-cloud/",
        headers={"X-Tapis-Token": jwt},
    )
    response.raise_for_status()
    point_cloud_list = response.json()

    # Build multiple lookup maps for flexible matching
    # Map by: description (path), filename from files_info, and description as label
    pc_by_description = {}
    pc_by_filename = {}

    for pc in point_cloud_list:
        # Map by description (might be full path or label)
        if pc.get("description"):
            pc_by_description[pc["description"]] = pc

        # Map by filename from files_info
        files_info = pc.get("files_info") or []
        if files_info and len(files_info) > 0:
            filename = files_info[0].get("name", "")
            if filename:
                pc_by_filename[filename] = pc
                # Also map without extension
                if filename.endswith(".laz"):
                    pc_by_filename[filename[:-4]] = pc

    completed = []
    errors = []
    pending = []

    for laz in laz_files:
        # Try to find matching point cloud by various methods
        pc = None

        # 1. Try matching by full path in description
        if laz.path in pc_by_description:
            pc = pc_by_description[laz.path]
        # 2. Try matching by filename
        elif laz.name in pc_by_filename:
            pc = pc_by_filename[laz.name]
        # 3. Try matching by filename without extension
        elif laz.name.endswith(".laz") and laz.name[:-4] in pc_by_filename:
            pc = pc_by_filename[laz.name[:-4]]

        if pc:
            # Get task info (might be None)
            task = pc.get("task")

            if task:
                status = task.get("status", "UNKNOWN")
                task_created = task.get("created")
                task_updated = task.get("updated")
                task_description = task.get("description", "")
            else:
                status = "NO_TASK"
                task_created = None
                task_updated = None
                task_description = "No task associated"

            # Get filename from files_info
            files_info = pc.get("files_info") or []
            pc_filename = files_info[0].get("name", "") if files_info else ""

            entry = {
                "laz_file": laz,
                "point_cloud": pc,
                "point_cloud_id": pc.get("id"),
                "feature_id": pc.get(
                    "feature_id"
                ),  # This is the Hazmapper feature ID for URL
                "status": status,
                "task_created": task_created,
                "task_updated": task_updated,
                "task_description": task_description,
                "pc_filename": pc_filename,
                "pc_description": pc.get("description", ""),
            }

            if status == "FINISHED":
                completed.append(entry)
            else:
                errors.append(entry)
        else:
            pending.append(
                {
                    "laz_file": laz,
                    "point_cloud": None,
                    "point_cloud_id": None,
                    "feature_id": None,
                    "status": "PENDING",
                    "task_created": None,
                    "task_updated": None,
                    "task_description": "",
                    "pc_filename": "",
                    "pc_description": "",
                }
            )

    return completed, errors, pending, point_cloud_list


# =============================================================================
# DISPLAY FUNCTIONS
# =============================================================================


def display_status_summary(completed, errors, pending, hazmapper_uuid):
    """Display summary of all files."""
    clear_screen()
    print_header("Point Cloud Status Summary")
    print()

    total = len(completed) + len(errors) + len(pending)

    print(f"  Total LAZ files found: {total}")
    print()
    print(f"  ✓ Completed:  {len(completed):>5}")
    print(f"  ✗ Errors:     {len(errors):>5}")
    print(f"  ○ Pending:    {len(pending):>5}")
    print()

    if completed:
        total_size = sum(c["laz_file"].size for c in completed)
        print(f"  Completed data size: {format_size(total_size)}")

    if pending:
        pending_size = sum(p["laz_file"].size for p in pending)
        print(f"  Pending data size:   {format_size(pending_size)}")


def display_completed_files(completed, hazmapper_uuid, page_size=15):
    """Display completed files with pagination."""
    if not completed:
        print("\n  No completed files.")
        input("  Press Enter to continue...")
        return

    # Sort by task completion date (newest first)
    sorted_completed = sorted(
        completed, key=lambda x: x.get("task_updated", "") or "", reverse=True
    )

    total = len(sorted_completed)
    page = 0
    total_pages = (total + page_size - 1) // page_size

    while True:
        clear_screen()
        print_header(f"Completed Files ({total} total) - Page {page + 1}/{total_pages}")
        print()

        start = page * page_size
        end = min(start + page_size, total)

        print(f"  {'#':<4} {'File Name':<40} {'Size':>10} {'Completed':>18}")
        print_divider()

        for i in range(start, end):
            c = sorted_completed[i]
            name = c["laz_file"].name[:38]
            size = format_size(c["laz_file"].size)
            completed_at = format_datetime(c.get("task_updated", ""))
            print(f"  {i+1:<4} {name:<40} {size:>10} {completed_at:>18}")

        print()
        print_divider()
        print("  [n]ext  [p]rev  [v]iew details  [q]uit")
        print_divider()

        choice = input("  Choice: ").strip().lower()

        if choice == "n" and page < total_pages - 1:
            page += 1
        elif choice == "p" and page > 0:
            page -= 1
        elif choice == "v":
            idx = input("  Enter file # to view: ").strip()
            try:
                idx = int(idx) - 1
                if 0 <= idx < total:
                    display_file_detail(sorted_completed[idx], hazmapper_uuid)
            except ValueError:
                pass
        elif choice == "q":
            break


def display_error_files(errors, hazmapper_uuid):
    """Display files with errors."""
    if not errors:
        print("\n  No files with errors.")
        input("  Press Enter to continue...")
        return

    clear_screen()
    print_header(f"Files with Errors ({len(errors)} total)")
    print()

    for i, e in enumerate(errors, 1):
        print(f"  [{i}] {e['laz_file'].name}")
        print(f"      Status:      {e['status']}")
        if e.get("task_description"):
            print(f"      Error:       {e['task_description']}")
        print(f"      PC ID:       {e.get('point_cloud_id', 'N/A')}")
        print(f"      Started:     {format_datetime(e.get('task_created', ''))}")
        print(f"      Updated:     {format_datetime(e.get('task_updated', ''))}")
        if e.get("feature_id"):
            url = get_hazmapper_feature_url(hazmapper_uuid, e["feature_id"])
            print(f"      View in Map: {url}")
        else:
            print(f"      View in Map: (no feature_id - upload may be incomplete)")
        print()

    print_divider()
    input("  Press Enter to continue...")


def display_pending_files(pending, page_size=20):
    """Display pending files with pagination."""
    if not pending:
        print("\n  No pending files.")
        input("  Press Enter to continue...")
        return

    # Sort by file name (pending is list of dicts with 'laz_file' key)
    sorted_pending = sorted(pending, key=lambda p: p["laz_file"].name)

    total = len(sorted_pending)
    page = 0
    total_pages = (total + page_size - 1) // page_size

    while True:
        clear_screen()
        print_header(f"Pending Files ({total} total) - Page {page + 1}/{total_pages}")
        print()

        start = page * page_size
        end = min(start + page_size, total)

        print(f"  {'#':<5} {'File Name':<50} {'Size':>12}")
        print_divider()

        for i in range(start, end):
            p = sorted_pending[i]
            name = p["laz_file"].name[:48]
            size = format_size(p["laz_file"].size)
            print(f"  {i+1:<5} {name:<50} {size:>12}")

        print()
        print_divider()
        print("  [n]ext  [p]rev  [q]uit")
        print_divider()

        choice = input("  Choice: ").strip().lower()

        if choice == "n" and page < total_pages - 1:
            page += 1
        elif choice == "p" and page > 0:
            page -= 1
        elif choice == "q":
            break


def display_file_detail(entry, hazmapper_uuid):
    """Display detailed info for a single file."""
    clear_screen()
    print_header("File Details")
    print()

    laz = entry["laz_file"]

    print("  SOURCE FILE (Tapis)")
    print_divider()
    print(f"  File Name:     {laz.name}")
    print(f"  Full Path:     {laz.path}")
    print(f"  Size:          {format_size(laz.size)}")
    print(
        f"  Last Modified: {laz.lastModified if hasattr(laz, 'lastModified') else 'N/A'}"
    )
    print()

    if entry.get("point_cloud"):
        print("  POINT CLOUD (Hazmapper)")
        print_divider()
        print(f"  Point Cloud ID:  {entry.get('point_cloud_id', 'N/A')}")
        print(f"  Feature ID:      {entry.get('feature_id', 'N/A')}")
        print(f"  Status:          {entry.get('status', 'N/A')}")
        print(f"  Description:     {entry.get('pc_description', 'N/A')}")
        print(f"  PC Filename:     {entry.get('pc_filename', 'N/A')}")
        print()

        print("  TASK INFO")
        print_divider()
        print(f"  Task Started:    {format_datetime(entry.get('task_created', ''))}")
        print(f"  Task Completed:  {format_datetime(entry.get('task_updated', ''))}")
        if entry.get("task_description"):
            print(f"  Task Message:    {entry.get('task_description')}")
        print()

        if entry.get("feature_id"):
            url = get_hazmapper_feature_url(hazmapper_uuid, entry["feature_id"])
            print(f"  View in Hazmapper:")
            print(f"  {url}")
        else:
            print("  (No feature_id - cannot generate Hazmapper link)")
    else:
        print("  POINT CLOUD (Hazmapper)")
        print_divider()
        print("  Not yet uploaded to Hazmapper")

    print()
    input("  Press Enter to continue...")


def view_all_point_clouds(hazmapper_project_id, hazmapper_uuid, page_size=15):
    """View all point clouds in the Hazmapper project (raw API data)."""
    response = requests.get(
        f"{HAZMAPPER_BACKEND}/projects/{hazmapper_project_id}/point-cloud/",
        headers={"X-Tapis-Token": jwt},
    )
    response.raise_for_status()
    point_clouds = response.json()

    if not point_clouds:
        print("\n  No point clouds in this Hazmapper project.")
        input("  Press Enter to continue...")
        return

    # Sort by description (point clouds are dicts from API)
    sorted_pcs = sorted(point_clouds, key=lambda pc: pc.get("description", "") or "")

    total = len(sorted_pcs)
    page = 0
    total_pages = (total + page_size - 1) // page_size

    while True:
        clear_screen()
        print_header(
            f"All Point Clouds ({total} total) - Page {page + 1}/{total_pages}"
        )
        print()

        start = page * page_size
        end = min(start + page_size, total)

        print(
            f"  {'#':<4} {'PC ID':<8} {'Status':<12} {'Description':<35} {'Feat ID':<10}"
        )
        print_divider()

        for i in range(start, end):
            pc = sorted_pcs[i]
            pc_id = pc.get("id", "N/A")
            task = pc.get("task") or {}
            status = task.get("status", "NO_TASK")
            desc = (pc.get("description", "") or "")[:33]
            feat_id = pc.get("feature_id") or "None"
            print(f"  {i+1:<4} {pc_id:<8} {status:<12} {desc:<35} {feat_id:<10}")

        print()
        print_divider()
        print("  [n]ext  [p]rev  [v]iew details  [d]elete  [q]uit")
        print_divider()

        choice = input("  Choice: ").strip().lower()

        if choice == "n" and page < total_pages - 1:
            page += 1
        elif choice == "p" and page > 0:
            page -= 1
        elif choice == "v":
            idx = input("  Enter # to view: ").strip()
            try:
                idx = int(idx) - 1
                if 0 <= idx < total:
                    display_point_cloud_detail(sorted_pcs[idx], hazmapper_uuid)
            except ValueError:
                pass
        elif choice == "d":
            idx = input("  Enter # to delete: ").strip()
            try:
                idx = int(idx) - 1
                if 0 <= idx < total:
                    if delete_point_cloud(hazmapper_project_id, sorted_pcs[idx]):
                        # Refresh the list
                        response = requests.get(
                            f"{HAZMAPPER_BACKEND}/projects/{hazmapper_project_id}/point-cloud/",
                            headers={"X-Tapis-Token": jwt},
                        )
                        response.raise_for_status()
                        point_clouds = response.json()
                        sorted_pcs = sorted(
                            point_clouds,
                            key=lambda pc: pc.get("description", "") or "",
                        )
                        total = len(sorted_pcs)
                        total_pages = (total + page_size - 1) // page_size
                        if page >= total_pages:
                            page = max(0, total_pages - 1)
            except ValueError:
                pass
        elif choice == "q":
            break


def display_point_cloud_detail(pc, hazmapper_uuid):
    """Display raw point cloud details from API."""
    clear_screen()
    print_header("Point Cloud Details (Raw API)")
    print()

    print(f"  Point Cloud ID:  {pc.get('id')}")
    print(f"  Feature ID:      {pc.get('feature_id')}")
    print(f"  Project ID:      {pc.get('project_id')}")
    print(f"  Description:     {pc.get('description')}")
    print()

    files_info = pc.get("files_info") or []
    if files_info:
        print("  FILES INFO:")
        for f in files_info:
            print(f"    - {f.get('name', 'Unknown')}")
    else:
        print("  FILES INFO: None")
    print()

    task = pc.get("task")
    if task:
        print("  TASK:")
        print(f"    ID:          {task.get('id')}")
        print(f"    Status:      {task.get('status')}")
        print(f"    Description: {task.get('description') or '(none)'}")
        print(f"    Created:     {format_datetime(task.get('created'))}")
        print(f"    Updated:     {format_datetime(task.get('updated'))}")
    else:
        print("  TASK: None (no conversion task)")
    print()

    if pc.get("feature_id"):
        url = get_hazmapper_feature_url(hazmapper_uuid, pc["feature_id"])
        print(f"  View in Hazmapper:")
        print(f"  {url}")

    print()
    input("  Press Enter to continue...")


def delete_point_cloud(hazmapper_project_id, pc):
    """Delete a point cloud from Hazmapper."""
    pc_id = pc.get("id")
    desc = pc.get("description", "Unknown")

    print()
    print(f"  About to delete Point Cloud ID: {pc_id}")
    print(f"  Description: {desc}")
    confirm = input("  Are you sure? [y/N]: ").strip().lower()

    if confirm != "y":
        print("  Cancelled.")
        input("  Press Enter to continue...")
        return False

    try:
        response = requests.delete(
            f"{HAZMAPPER_BACKEND}/projects/{hazmapper_project_id}/point-cloud/{pc_id}/",
            headers={"X-Tapis-Token": jwt},
        )
        response.raise_for_status()
        print(f"  ✓ Deleted successfully!")
        input("  Press Enter to continue...")
        return True
    except Exception as e:
        print(f"  ✗ Delete failed: {e}")
        input("  Press Enter to continue...")
        return False


def manage_error_files(config, errors):
    """Manage files with errors - retry or delete."""
    hazmapper_project_id = config["hazmapper_project_id"]
    hazmapper_uuid = config["hazmapper_uuid"]
    system_id = config["system_id"]

    while True:
        clear_screen()
        print_header(f"Manage Error Files ({len(errors)} total)")
        print()

        for i, e in enumerate(errors, 1):
            status = e.get("status", "UNKNOWN")
            print(f"  [{i}] {e['laz_file'].name}")
            print(f"      Status: {status} | PC ID: {e.get('point_cloud_id', 'N/A')}")

        print()
        print_divider()
        print("  Options:")
        print("  [d #] Delete point cloud (e.g., 'd 1')")
        print("  [D]   Delete ALL failed point clouds")
        print("  [r #] Retry file (delete + re-upload)")
        print("  [R]   Retry ALL failed files")
        print("  [q]   Quit to main menu")
        print_divider()

        choice = input("  Choice: ").strip()

        if choice.lower() == "q":
            break

        elif choice.lower().startswith("d "):
            # Delete single
            try:
                idx = int(choice[2:].strip()) - 1
                if 0 <= idx < len(errors):
                    pc = errors[idx].get("point_cloud")
                    if pc:
                        if delete_point_cloud_silent(hazmapper_project_id, pc):
                            print(f"  ✓ Deleted {errors[idx]['laz_file'].name}")
                    else:
                        print("  No point cloud to delete for this file.")
            except (ValueError, IndexError):
                print("  Invalid selection.")
            input("  Press Enter to continue...")

        elif choice.upper() == "D":
            # Delete all
            confirm = (
                input(f"  Delete ALL {len(errors)} failed point clouds? [y/N]: ")
                .strip()
                .lower()
            )
            if confirm == "y":
                deleted = 0
                for e in errors:
                    pc = e.get("point_cloud")
                    if pc:
                        if delete_point_cloud_silent(hazmapper_project_id, pc):
                            deleted += 1
                            print(f"  ✓ Deleted {e['laz_file'].name}")
                print(f"\n  Deleted {deleted} point clouds.")
            input("  Press Enter to continue...")
            break

        elif choice.lower().startswith("r "):
            # Retry single
            try:
                idx = int(choice[2:].strip()) - 1
                if 0 <= idx < len(errors):
                    e = errors[idx]
                    pc = e.get("point_cloud")
                    laz = e["laz_file"]

                    print(f"  Retrying: {laz.name}")

                    # Delete existing if present
                    if pc:
                        delete_point_cloud_silent(hazmapper_project_id, pc)
                        print("  ✓ Deleted old point cloud")

                    # Create new
                    ok, pc_id = create_point_cloud_feature(
                        hazmapper_project_id, system_id, laz
                    )
                    if ok:
                        print(f"  ✓ Re-submitted with PC ID: {pc_id}")
                    else:
                        print("  ✗ Failed to re-submit")
            except (ValueError, IndexError):
                print("  Invalid selection.")
            input("  Press Enter to continue...")

        elif choice.upper() == "R":
            # Retry all
            confirm = (
                input(f"  Retry ALL {len(errors)} failed files? [y/N]: ")
                .strip()
                .lower()
            )
            if confirm == "y":
                for e in errors:
                    pc = e.get("point_cloud")
                    laz = e["laz_file"]

                    print(f"  Retrying: {laz.name}")

                    if pc:
                        delete_point_cloud_silent(hazmapper_project_id, pc)

                    ok, pc_id = create_point_cloud_feature(
                        hazmapper_project_id, system_id, laz
                    )
                    if ok:
                        print(f"    ✓ Submitted with PC ID: {pc_id}")
                    else:
                        print("    ✗ Failed")

                    time.sleep(5)  # Shorter delay for retries

                print("\n  Retry complete!")
            input("  Press Enter to continue...")
            break


def delete_point_cloud_silent(hazmapper_project_id, pc):
    """Delete a point cloud without prompting."""
    pc_id = pc.get("id")
    try:
        response = requests.delete(
            f"{HAZMAPPER_BACKEND}/projects/{hazmapper_project_id}/point-cloud/{pc_id}/",
            headers={"X-Tapis-Token": jwt},
        )
        response.raise_for_status()
        return True
    except Exception:
        return False


def watch_point_clouds(hazmapper_project_id, hazmapper_uuid, poll_interval=30):
    """
    Watch point cloud processing until all tasks reach terminal state.
    Polls the API and displays live status updates.
    """
    print()
    print_header("Watching Point Cloud Processing")
    print()
    print(f"  Polling every {poll_interval} seconds. Press Ctrl+C to stop.")
    print()

    iteration = 0

    try:
        while True:
            iteration += 1

            # Fetch current status
            try:
                response = requests.get(
                    f"{HAZMAPPER_BACKEND}/projects/{hazmapper_project_id}/point-cloud/",
                    headers={"X-Tapis-Token": jwt},
                )
                response.raise_for_status()
                point_clouds = response.json()
            except Exception as e:
                print(f"  ✗ Error fetching status: {e}")
                print(f"    Retrying in {poll_interval}s...")
                time.sleep(poll_interval)
                continue

            # Categorize by status
            in_progress = []
            finished = []
            failed = []
            no_task = []

            for pc in point_clouds:
                task = pc.get("task")
                if not task:
                    no_task.append(pc)
                else:
                    status = task.get("status", "UNKNOWN")
                    if status == "FINISHED":
                        finished.append(pc)
                    elif status in TERMINAL_STATES:
                        failed.append(pc)
                    else:
                        in_progress.append(pc)

            # Clear and display status
            clear_screen()
            print_header("Watching Point Cloud Processing")
            print()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"  Last updated: {now} (poll #{iteration})")
            print(f"  Poll interval: {poll_interval}s | Press Ctrl+C to stop")
            print()
            print_divider()
            print(f"  SUMMARY")
            print_divider()
            print(f"  ✓ Finished:    {len(finished):>5}")
            print(f"  ✗ Failed:      {len(failed):>5}")
            print(f"  ◐ In Progress: {len(in_progress):>5}")
            print(f"  ? No Task:     {len(no_task):>5}")
            print(f"  ─────────────────────")
            print(f"  Total:         {len(point_clouds):>5}")
            print()

            # Show in-progress details
            if in_progress:
                print_divider()
                print(f"  IN PROGRESS ({len(in_progress)})")
                print_divider()

                # Sort by task created time
                in_progress_sorted = sorted(
                    in_progress,
                    key=lambda x: (x.get("task") or {}).get("created", "") or "",
                )

                # Show up to 20
                display_count = min(20, len(in_progress_sorted))
                for pc in in_progress_sorted[:display_count]:
                    task = pc.get("task", {})
                    status = task.get("status", "UNKNOWN")
                    desc = (pc.get("description", "") or "")[:40]
                    pc_id = pc.get("id", "N/A")
                    created = format_datetime(task.get("created", ""))

                    # Status indicator
                    if status in ("QUEUED", "PENDING"):
                        indicator = "◯"
                    elif status in ("RUNNING", "PROCESSING"):
                        indicator = "◐"
                    else:
                        indicator = "?"

                    print(f"  {indicator} [{pc_id}] {status:<10} {desc}")

                if len(in_progress) > display_count:
                    print(f"  ... and {len(in_progress) - display_count} more")
                print()

            # Show recent failures
            if failed:
                print_divider()
                print(f"  FAILED ({len(failed)})")
                print_divider()

                # Show up to 10 failures
                display_count = min(10, len(failed))
                for pc in failed[:display_count]:
                    task = pc.get("task", {})
                    status = task.get("status", "UNKNOWN")
                    desc = (pc.get("description", "") or "")[:35]
                    pc_id = pc.get("id", "N/A")
                    error_msg = (task.get("description", "") or "")[:30]

                    print(f"  ✗ [{pc_id}] {desc}")
                    if error_msg:
                        print(f"           Error: {error_msg}")

                if len(failed) > display_count:
                    print(f"  ... and {len(failed) - display_count} more")
                print()

            # Check if all done
            if len(in_progress) == 0:
                print_divider()
                print("  ✓ All tasks have reached terminal state!")
                print_divider()
                print()
                print(f"  Final Results:")
                print(f"    Finished: {len(finished)}")
                print(f"    Failed:   {len(failed)}")

                if failed:
                    print()
                    print(
                        "  Failed items need attention. Use option [8] from main menu"
                    )
                    print("  to retry or delete failed uploads.")

                print()
                break

            # Wait for next poll
            print_divider()
            print(f"  Waiting {poll_interval}s for next update...")

            # Show countdown
            for remaining in range(poll_interval, 0, -1):
                sys.stdout.write(f"\r  Next poll in {remaining:>3}s... ")
                sys.stdout.flush()
                time.sleep(1)
            print()

    except KeyboardInterrupt:
        print("\n")
        print("  Watch stopped by user.")
        print()

    input("  Press Enter to continue...")


def watch_specific_ids(hazmapper_project_id, hazmapper_uuid, pc_ids, poll_interval=30):
    """
    Watch specific point cloud IDs until they reach terminal state.
    Useful after submitting a batch.
    """
    print()
    print_header(f"Watching {len(pc_ids)} Point Clouds")
    print()
    print(
        f"  Tracking IDs: {', '.join(map(str, pc_ids[:5]))}{'...' if len(pc_ids) > 5 else ''}"
    )
    print(f"  Polling every {poll_interval} seconds. Press Ctrl+C to stop.")
    print()

    try:
        while True:
            # Fetch current status
            try:
                response = requests.get(
                    f"{HAZMAPPER_BACKEND}/projects/{hazmapper_project_id}/point-cloud/",
                    headers={"X-Tapis-Token": jwt},
                )
                response.raise_for_status()
                all_pcs = response.json()
            except Exception as e:
                print(f"  ✗ Error fetching status: {e}")
                time.sleep(poll_interval)
                continue

            # Filter to our IDs
            pc_map = {pc.get("id"): pc for pc in all_pcs}
            tracked = [pc_map.get(pid) for pid in pc_ids if pid in pc_map]

            in_progress = []
            finished = []
            failed = []

            for pc in tracked:
                if not pc:
                    continue
                task = pc.get("task")
                if not task:
                    in_progress.append(pc)  # No task yet
                else:
                    status = task.get("status", "UNKNOWN")
                    if status == "FINISHED":
                        finished.append(pc)
                    elif status in TERMINAL_STATES:
                        failed.append(pc)
                    else:
                        in_progress.append(pc)

            # Display
            clear_screen()
            now = datetime.now().strftime("%H:%M:%S")
            print(f"  [{now}] Tracking {len(tracked)} point clouds")
            print()
            print(f"  ✓ Finished:    {len(finished):>3} / {len(tracked)}")
            print(f"  ✗ Failed:      {len(failed):>3}")
            print(f"  ◐ In Progress: {len(in_progress):>3}")
            print()

            # Show in-progress
            if in_progress:
                for pc in in_progress[:10]:
                    task = pc.get("task") or {}
                    status = task.get("status", "WAITING")
                    desc = (pc.get("description", "") or "")[:50]
                    print(f"  ◐ {status:<10} {desc}")
                if len(in_progress) > 10:
                    print(f"  ... +{len(in_progress) - 10} more")

            # Check if done
            if len(in_progress) == 0:
                print()
                print_divider()
                print(f"  ✓ All {len(tracked)} tasks complete!")
                print(f"    Finished: {len(finished)} | Failed: {len(failed)}")
                print_divider()
                break

            # Wait
            for remaining in range(poll_interval, 0, -1):
                sys.stdout.write(f"\r  Next poll in {remaining}s... ")
                sys.stdout.flush()
                time.sleep(1)
            print()

    except KeyboardInterrupt:
        print("\n  Watch stopped.")

    input("\n  Press Enter to continue...")


# =============================================================================
# PROCESSING
# =============================================================================


def select_files_to_process(pending):
    """Interactive file selection for processing."""
    if not pending:
        return []

    while True:
        clear_screen()
        print_header("Select Files to Process")
        print()
        print(f"  Total pending files: {len(pending)}")
        print()
        print_divider()
        print("  Options:")
        print_divider()
        print("  [1] Process ALL pending files")
        print("  [2] Process first N files")
        print("  [3] Select specific files by number")
        print("  [4] Select a range (e.g., 1-50)")
        print("  [5] View pending file list")
        print("  [6] Cancel - return to main menu")
        print()

        choice = input("  Choice (1-6): ").strip()

        # Sort by name (pending is list of dicts with 'laz_file' key)
        sorted_pending = sorted(pending, key=lambda p: p["laz_file"].name)

        if choice == "1":
            return [p["laz_file"] for p in sorted_pending]

        elif choice == "2":
            n = input(f"  How many files? (1-{len(pending)}): ").strip()
            try:
                n = int(n)
                if 1 <= n <= len(pending):
                    return [p["laz_file"] for p in sorted_pending[:n]]
            except ValueError:
                pass
            print("  Invalid number.")
            input("  Press Enter to continue...")

        elif choice == "3":
            print(f"  Enter file numbers separated by commas (1-{len(pending)})")
            nums = input("  Selection: ").strip()
            try:
                indices = [int(x.strip()) - 1 for x in nums.split(",")]
                selected = [
                    sorted_pending[i]["laz_file"]
                    for i in indices
                    if 0 <= i < len(pending)
                ]
                if selected:
                    return selected
            except (ValueError, IndexError):
                pass
            print("  Invalid selection.")
            input("  Press Enter to continue...")

        elif choice == "4":
            range_str = input(f"  Enter range (e.g., 1-50): ").strip()
            try:
                start, end = range_str.split("-")
                start = int(start.strip()) - 1
                end = int(end.strip())
                if 0 <= start < end <= len(pending):
                    return [p["laz_file"] for p in sorted_pending[start:end]]
            except ValueError:
                pass
            print("  Invalid range.")
            input("  Press Enter to continue...")

        elif choice == "5":
            display_pending_files(pending)

        elif choice == "6":
            return []


def confirm_processing(files):
    """Confirm before processing."""
    clear_screen()
    print_header("Confirm Processing")
    print()
    print(f"  Files to process: {len(files)}")

    total_size = sum(f.size for f in files)
    print(f"  Total data size: {format_size(total_size)}")
    print()

    if len(files) <= 10:
        print("  Files:")
        for f in files:
            print(f"    - {f.name} ({format_size(f.size)})")
        print()

    confirm = input("  Proceed? [y/N]: ").strip().lower()
    return confirm == "y"


def create_point_cloud_feature(hazmapper_project_id, system_id, laz_file):
    """Create a point cloud feature for a LAZ file.
    Returns: (success, point_cloud_id)
    Note: feature_id is assigned later when the conversion task completes.
    """
    try:
        # Use the full path as description for easier matching later
        data = {"description": laz_file.path}
        response = requests.post(
            f"{HAZMAPPER_BACKEND}/projects/{hazmapper_project_id}/point-cloud/",
            json=data,
            headers={"X-Tapis-Token": jwt},
        )
        response.raise_for_status()
        point_cloud_id = response.json()["id"]

        response = requests.post(
            f"{HAZMAPPER_BACKEND}/projects/{hazmapper_project_id}/point-cloud/{point_cloud_id}/import/",
            json={"files": [{"system": system_id, "path": laz_file.path}]},
            headers={"X-Tapis-Token": jwt},
        )
        response.raise_for_status()
        return True, point_cloud_id
    except Exception as e:
        logging.error(f"Failed: {laz_file.path} - {e}")
        return False, None


def process_files(config, files):
    """Process selected files with progress display."""
    hazmapper_project_id = config["hazmapper_project_id"]
    hazmapper_uuid = config["hazmapper_uuid"]
    system_id = config["system_id"]

    total = len(files)
    success = 0
    failed = 0
    results = []

    print()
    print_header("Processing Files")
    print()
    print("  Note: Point cloud ID is shown immediately. Feature ID (for map links)")
    print("        is assigned after the conversion task completes.")
    print()

    for i, laz_file in enumerate(files, 1):
        print(f"  [{i}/{total}] {laz_file.name}")

        ok, pc_id = create_point_cloud_feature(
            hazmapper_project_id, system_id, laz_file
        )

        if ok:
            success += 1
            print(f"         ✓ Submitted - Point Cloud ID: {pc_id}")
            results.append({"file": laz_file.name, "status": "success", "pc_id": pc_id})
        else:
            failed += 1
            print(f"         ✗ Failed to submit")
            results.append({"file": laz_file.name, "status": "failed", "pc_id": None})

        if i < total and DELAY_BETWEEN_FILES > 0:
            time.sleep(DELAY_BETWEEN_FILES)

    print()
    print_divider()
    print(f"  Processing complete!")
    print(f"  Submitted: {success}")
    print(f"  Failed:    {failed}")
    print()
    print("  Run 'Refresh status' from main menu to see completion progress.")
    print_divider()

    return results


# =============================================================================
# MAIN MENU
# =============================================================================


def main_menu(config, completed, errors, pending):
    """Main interactive menu."""
    hazmapper_uuid = config["hazmapper_uuid"]
    hazmapper_project_id = config["hazmapper_project_id"]

    while True:
        clear_screen()
        print_header("LAZ Point Cloud Processor - Main Menu")
        print()
        print(f"  Map:     {config['hazmapper_name']}")
        print(f"  Project: {config['prj_number']} - {config['project_title'][:45]}")
        print(
            f"  Paths:   {', '.join(config['paths'][:2])}{'...' if len(config['paths']) > 2 else ''}"
        )
        print()
        print_divider()
        print(
            f"  Status:  ✓ {len(completed)} completed | ✗ {len(errors)} errors | ○ {len(pending)} pending"
        )
        print_divider()
        print()
        print("  FILE STATUS")
        print("  [1] View completed files")
        print("  [2] View files with errors")
        print("  [3] View pending files")
        print()
        print("  ACTIONS")
        print("  [4] Process pending files")
        print("  [5] Refresh status")
        print("  [6] Watch in-progress tasks")
        print()
        print("  ADVANCED")
        print("  [7] View all point clouds (raw API)")
        print("  [8] Retry/delete failed uploads")
        print()
        print("  [0] Exit")
        print()

        choice = input("  Choice: ").strip()

        if choice == "1":
            display_completed_files(completed, hazmapper_uuid)

        elif choice == "2":
            display_error_files(errors, hazmapper_uuid)

        elif choice == "3":
            display_pending_files(pending)

        elif choice == "4":
            if not pending:
                print("\n  No pending files to process!")
                input("  Press Enter to continue...")
            else:
                selected = select_files_to_process(pending)
                if selected and confirm_processing(selected):
                    results = process_files(config, selected)

                    # Offer to watch
                    pc_ids = [r["pc_id"] for r in results if r.get("pc_id")]
                    if pc_ids:
                        watch = input("\n  Watch progress? [Y/n]: ").strip().lower()
                        if watch != "n":
                            watch_specific_ids(
                                hazmapper_project_id, hazmapper_uuid, pc_ids
                            )
                    else:
                        input("\n  Press Enter to continue...")
                    return "refresh"

        elif choice == "5":
            return "refresh"

        elif choice == "6":
            watch_point_clouds(hazmapper_project_id, hazmapper_uuid)

        elif choice == "7":
            view_all_point_clouds(hazmapper_project_id, hazmapper_uuid)

        elif choice == "8":
            if not errors:
                print("\n  No files with errors!")
                input("  Press Enter to continue...")
            else:
                manage_error_files(config, errors)
                return "refresh"

        elif choice == "0":
            return "exit"


def get_watch_only_config():
    """Minimal configuration for watch-only mode."""
    config = {}
    saved_config = load_saved_config()

    # Get credentials
    username, password = get_credentials(saved_config)
    if not authenticate(username, password):
        return None

    config["username"] = username

    # Check if we have saved hazmapper config
    if saved_config and saved_config.get("hazmapper_uuid"):
        print()
        print(f"  Saved map: {saved_config.get('hazmapper_name', 'N/A')}")
        use_saved = input("  Use saved map? [Y/n]: ").strip().lower()

        if use_saved != "n":
            print("  → Validating...")
            hazmapper_info = get_hazmapper_project_info(saved_config["hazmapper_uuid"])
            if hazmapper_info:
                config["hazmapper_uuid"] = saved_config["hazmapper_uuid"]
                config["hazmapper_project_id"] = hazmapper_info["id"]
                config["hazmapper_name"] = hazmapper_info["name"]
                print(f"  ✓ Connected to: {hazmapper_info['name']}")
                return config
            else:
                print("  ✗ Saved map no longer accessible.")

    print()
    print("  Enter the Hazmapper map URL to watch:")

    while True:
        hazmapper_url = input("  Hazmapper URL: ").strip()
        hazmapper_uuid = parse_hazmapper_url(hazmapper_url)

        if not hazmapper_uuid:
            print("  ✗ Could not parse UUID from URL.")
            continue

        print(f"  → Fetching Hazmapper project info...")
        hazmapper_info = get_hazmapper_project_info(hazmapper_uuid)

        if not hazmapper_info:
            print("  ✗ Could not find Hazmapper project.")
            continue

        print(f"  ✓ Found map: {hazmapper_info['name']}")

        config["hazmapper_uuid"] = hazmapper_uuid
        config["hazmapper_project_id"] = hazmapper_info["id"]
        config["hazmapper_name"] = hazmapper_info["name"]
        return config


def main():
    # Startup menu
    clear_screen()
    print_header("LAZ Point Cloud Processor for Hazmapper")
    print()
    print("  What would you like to do?")
    print()
    print("  [1] Process files")
    print("  [2] Watch in-progress tasks only")
    print()
    print("  [0] Exit")
    print()

    choice = input("  Choice: ").strip()

    if choice == "0":
        print("\n  Goodbye!")
        return

    if choice == "2":
        # Watch-only mode
        config = get_watch_only_config()
        if not config:
            print("  Configuration failed. Exiting.")
            sys.exit(1)

        watch_point_clouds(
            config["hazmapper_project_id"],
            config["hazmapper_uuid"],
            poll_interval=10,
        )
        return

    if choice != "1":
        print("  Invalid choice.")
        return

    # Full interactive mode
    config = get_config_interactive()
    if not config:
        print("  Configuration failed. Exiting.")
        sys.exit(1)

    while True:
        # Scan and get status
        clear_screen()
        print_header("Scanning Files")
        print()

        laz_files = get_laz_files(config["system_id"], config["paths"])

        if not laz_files:
            print("  No .laz files found!")
            sys.exit(0)

        print(f"\n  Total LAZ files: {len(laz_files)}")
        print("  Checking point cloud status...")

        completed, errors, pending, _ = get_point_cloud_status(
            config["hazmapper_project_id"], laz_files
        )

        display_status_summary(completed, errors, pending, config["hazmapper_uuid"])
        input("\n  Press Enter to continue to main menu...")

        # Main menu loop
        result = main_menu(config, completed, errors, pending)

        if result == "exit":
            print("\n  Goodbye!")
            break
        elif result == "refresh":
            continue


if __name__ == "__main__":
    main()
