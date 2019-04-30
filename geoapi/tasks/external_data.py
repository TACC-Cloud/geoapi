from geoapi.celery_app import app
from geoapi.models import User, ObservableDataProject, Project
from geoapi.utils import tenants
from geoapi.utils.agave import AgaveUtils
from geoapi.log import logging

logger = logging.getLogger(__file__)

@app.task()
def import_from_agave(user: User, systemId: str, path: str, proj: Project):
    api_server = tenants.get_api_server(user.tenant_id)
    # client = Agave(jwt=user.jwt,
    #               jwt_header_name='X-JWT-Assertion-{tenant}'.format(tenant=user.tenant_id),
    #               api_server='http://api.prod.tacc.cloud'
    #            )
    # listing = client.files.list(systemId=systemId, filePath=path)
    # logger.info(listing)
    client = AgaveUtils(user.jwt)
    listing = client.listing(systemId, path)
    logger.info(listing)
    # First item is always a reference to self
    for item in listing[1:]:
        if item.type == "dir":
            import_from_agave(user, systemId, item.path, proj)
        else:
            logger.info(item)
            listing = client.listing(systemId, item.path)
            logger.info(listing)
            f = client.getFile(systemId, item.path)
            meta = client.getMetaAssociated(item.uuid)
            logger.info(meta)

@app.task()
def refresh_observable_projects():
    obs = ObservableDataProject.query.all()
    logger.info(obs)
    for o in obs:
        import_from_agave(o.project.users[0], o.system_id, o.path, o.project)


if __name__ =="__main__":
    u = User.query.get(1)
    refresh_observable_projects()