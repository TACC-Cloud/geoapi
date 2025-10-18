from typing import List, Dict, Tuple
from celery import uuid as celery_uuid

from geoapi.models import TileServer, Task, User
from geoapi.schema.tapis import TapisFilePath
from geoapi.log import logger
from geoapi.utils.assets import delete_assets


class TileService:
    """
    Central location of all interactions with tile servers.
    """

    @staticmethod
    def addTileServer(database_session, projectId: int, data: Dict):
        """
        :param projectId: int
        :param data: Dict
        :return: ts: TileServer
        """
        ts = TileServer()

        for key, value in data.items():
            setattr(ts, key, value)

        ts.project_id = projectId

        database_session.add(ts)
        database_session.commit()
        return ts

    @staticmethod
    def getTileServers(database_session, projectId: int) -> List[TileServer]:
        tile_servers = (
            database_session.query(TileServer).filter_by(project_id=projectId).all()
        )
        return tile_servers

    @staticmethod
    def deleteTileServer(database_session, tile_server_id: int) -> None:
        ts = database_session.get(TileServer, tile_server_id)

        uuid_str = str(ts.uuid) if ts.uuid else None

        database_session.delete(ts)
        database_session.commit()

        # cleanup asset file (if they exist)
        if uuid_str:
            delete_assets(projectId=ts.project_id, uuid=uuid_str)

    @staticmethod
    def updateTileServer(database_session, tileServerId: int, data: dict):
        ts = database_session.get(TileServer, tileServerId)
        for key, value in data.items():
            setattr(ts, key, value)
        database_session.commit()
        return ts

    @staticmethod
    def updateTileServers(database_session, dataList: List[dict]):
        ret_list = []
        for tsv in dataList:
            ts = database_session.get(TileServer, int(tsv["id"]))
            for key, value in tsv.items():
                setattr(ts, key, value)
            ret_list.append(ts)
            database_session.commit()
        return ret_list

    def import_tile_server_files(
        database_session,
        user: User,
        project_id: int,
        files: list[TapisFilePath],
    ) -> list[Task]:
        """
        Queue conversion of raster(s) at Tapis paths into COGs and register tile servers.
        Returns a list of Task rows (one per file).
        """
        from geoapi.tasks.raster import import_tile_servers_from_tapis

        pending_tasks: list[Tuple[int, str, TapisFilePath]] = []

        # Create tasks and flush to get IDs
        for f in files:
            celery_task_uuid = celery_uuid()
            task = Task(
                process_id=celery_task_uuid,
                status="QUEUED",
                description=f"Add tile-server for {f.path}",
                project_id=project_id,
            )
            database_session.add(task)
            database_session.flush()  # assigns task.id
            pending_tasks.append((task.id, celery_task_uuid, f.model_dump()))

            logger.info(
                f"Prepared importing proj:{project_id} user:{user.username} file:{f}",
            )

        # commit tasks
        database_session.commit()

        failed: list[int] = []
        for task_db_id, celery_task_uuid, tapis_fileas_dict in pending_tasks:
            try:
                import_tile_servers_from_tapis.apply_async(
                    kwargs={
                        "user_id": user.id,
                        "tapis_file": tapis_fileas_dict,
                        "project_id": project_id,
                        "task_id": task_db_id,
                    },
                    task_id=celery_task_uuid,
                )
            except Exception:
                logger.exception(
                    "Failed to publish Celery job for task_id=%s", task_db_id
                )
                failed.append(task_db_id)

        # Mark tasks as failed
        if failed:
            database_session.query(Task).filter(Task.id.in_(failed)).update(
                {"status": "error", "description": "Failed to enqueue background job"},
                synchronize_session=False,
            )
            database_session.commit()

        # Optionally re-query to return fresh rows
        task_ids = [tid for tid, _, _ in pending_tasks]
        return database_session.query(Task).filter(Task.id.in_(task_ids)).all()
