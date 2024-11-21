from geoapi.models import ObservableDataProject, Project
from geoapi.db import create_task_session
from geoapi.log import logger

# Check that migrations worked out as expected
# Remove this file with https://tacc-main.atlassian.net/browse/WG-377

with create_task_session() as session:
    observable_projects = session.query(ObservableDataProject).all()
    projects = session.query(Project).all()

    logger.info(
        f"Checking observable_projects ({len(observable_projects)}) and projects ({len(projects)})"
    )

    issues = 0
    for obs in observable_projects:
        try:
            if (
                not obs.project.watch_users
                or obs.watch_content != obs.project.watch_content
            ):
                issues += 1
                logger.info(
                    f"Issue with observable project (id:{obs.id} project_id:{obs.project_id}):\n"
                    f"   obs.project.watch_users:{obs.project.watch_users}\n"
                    f"   obs.project.watch_content:{obs.project.watch_content}\n"
                    f"   obs.project.watch_content:{obs.watch_content}\n"
                )
        except Exception:
            issues += 1
            logger.exception(
                f"Something happened when checking observable project"
                f" (id:{obs.id} project_id:{obs.project_id})"
            )

    logger.info(
        "\n\n\nDone checking.\n\nNote some discrepancies could occur (i.e. projects are deleted but then deprecated"
        " observable project is not deleted) \n\n"
    )
    logger.info(f"{issues} issues found.")
