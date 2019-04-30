import pathlib
from geoapi.celery_app import app
from geoapi.models import User, ObservableDataProject, Project, FeatureAsset, Feature
from geoapi.utils import tenants
from geoapi.utils.agave import AgaveUtils
from geoapi.log import logging
from geoapi.services.features import FeaturesService
logger = logging.getLogger(__file__)

def _get_file_and_metadata():
    pass


def _parse_rapid_geolocation(loc):
    coords = loc[0]
    lat = loc["latitude"]
    lon = loc["longitude"]
    return lat, lon


@app.task(rate_limit="5/s")
def import_from_agave(user: User, systemId: str, path: str, proj: Project):
    client = AgaveUtils(user.jwt)
    listing = client.listing(systemId, path)
    # First item is always a reference to self
    for item in listing[1:]:
        logger.info(item.path.suffix)
        if item.type == "dir":
            import_from_agave(user, systemId, item.path, proj)
        # skip any junk files that are not allowed
        if item.path.suffix.lower().lstrip('.') not in FeaturesService.ALLOWED_EXTENSIONS:
            logger.info("Skipping {}".format(item.path))
            continue
        else:
            # first check if there already is a file in the DB
            asset = FeatureAsset.query.filter(FeatureAsset.original_path == str(item.path)).first()
            if asset:
                logger.info("Already imported {}".format(item.path))
                continue
            listing = client.listing(systemId, item.path)[0]
            # f = client.getFile(systemId, item.path)
            meta = client.getMetaAssociated(listing.uuid)
            if not meta:
                logger.info("No metadata for {}".format(item.path))
                continue
            geolocation = meta.get("geolocation")
            lat, lon = _parse_rapid_geolocation(geolocation)
            if not geolocation:
                logger.info("NO geolocation for {}".format(item.path))
                continue
            logger.info(geolocation)
            # f = client.getFile(systemId, item.path)



@app.task()
def refresh_observable_projects():
    obs = ObservableDataProject.query.all()
    logger.info(obs)
    for o in obs:
        import_from_agave(o.project.users[0], o.system_id, o.path, o.project)


if __name__ =="__main__":
    u = User.query.get(1)
    refresh_observable_projects()