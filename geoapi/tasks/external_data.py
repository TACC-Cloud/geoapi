import os
from pathlib import Path
from geoapi.celery_app import app
from geoapi.models import User, ObservableDataProject, Project, FeatureAsset
from geoapi.exceptions import ApiException
from geoapi.utils.agave import AgaveUtils
from geoapi.log import logging
import geoapi.services.features as features

from geoapi.db import db_session
logger = logging.getLogger(__file__)

def _get_file_and_metadata():
    pass


def _parse_rapid_geolocation(loc):
    coords = loc[0]
    lat = coords["latitude"]
    lon = coords["longitude"]
    return lat, lon

@app.task(rate_limit="1/s")
def import_file_from_agave(jwt: str, systemId: str, path: str, projectId: int):
    client = AgaveUtils(jwt)
    try:
        tmp_file_uuid = client.getFile(systemId, path)
        fpath = Path(path)
        pth = Path("/tmp/" + tmp_file_uuid)
        with pth.open("rb") as f:
            f.filename = fpath.name
            features.FeaturesService.fromFileObj(projectId, f, {}, path)
        os.remove(os.path.join('/tmp', tmp_file_uuid))
    except Exception as e:
        logger.error("Could not import file from agave: {} :: {}".format(systemId, path), e)



#TODO: Add users to project based on the agave users on the system.
#TODO: This is an abomination
@app.task(rate_limit="5/s")
def import_from_agave(user: User, systemId: str, path: str, proj: Project):
    client = AgaveUtils(user.jwt)
    listing = client.listing(systemId, path)
    # First item is always a reference to self
    for item in listing[1:]:
        if item.type == "dir":
            import_from_agave(user, systemId, item.path, proj)
        # skip any junk files that are not allowed
        if item.path.suffix.lower().lstrip('.') not in features.FeaturesService.ALLOWED_EXTENSIONS:
            continue
        else:
            try:
                # first check if there already is a file in the DB
                item_system_path = os.path.join(item.system, str(item.path).lstrip("/"))
                logger.info(item_system_path)

                asset = db_session.query(FeatureAsset).filter(FeatureAsset.original_path == item_system_path).first()
                if asset:
                    logger.info("Already imported {}".format(item_system_path))
                    continue

                # If its a RApp project folder, grab the metadata from tapis meta service
                if Path(item_system_path).match("*/RApp/*"):
                    logger.info("RApp import {path}".format(path=item_system_path))
                    listing = client.listing(systemId, item.path)[0]
                    # f = client.getFile(systemId, item.path)
                    meta = client.getMetaAssociated(listing.uuid)
                    if not meta:
                        logger.info("No metadata for {}".format(item.path))
                        continue
                    geolocation = meta.get("geolocation")
                    if not geolocation:
                        logger.info("NO geolocation for {}".format(item.path))
                        continue
                    lat, lon = _parse_rapid_geolocation(geolocation)
                    # 1) Get the file from agave, save to /tmp
                    # 2) Resize and thumbnail images or transcode video to mp4
                    # 3) create a FeatureAsset and a Feature
                    # 4) save the image/video to /assets
                    # 5) delete the original in /tmp

                    # client.getFile will save the asset to /tmp/{uuid}
                    tmp_file_uuid = client.getFile(systemId, item.path)
                    ext = item.ext
                    feat = features.FeaturesService.fromLatLng(proj.id, lat, lon, {})
                    feat.properties = meta
                    db_session.add(feat)
                    db_session.commit()
                    with open(os.path.join("/tmp", tmp_file_uuid), 'rb') as fd:
                        fd.filename = Path(item.path).name
                        if ext in features.FeaturesService.ALLOWED_EXTENSIONS:
                            fa = features.FeaturesService.createFeatureAsset(proj.id, feat.id, fd, original_path=path)
                        else:
                            raise ApiException("Could not process this file")
                    fa.feature = feat
                    fa.original_path = item_system_path
                    db_session.add(fa)
                    db_session.commit()
                    os.remove(os.path.join("/tmp", tmp_file_uuid))
                elif item.path.suffix.lower().lstrip('.') in features.FeaturesService.ALLOWED_GEOSPATIAL_EXTENSIONS:
                    tmp_file_uuid = client.getFile(systemId, item.path)
                    with open(os.path.join("/tmp", tmp_file_uuid), 'rb') as fd:
                        fd.filename = Path(item.path).name
                        features.FeaturesService.fromFileObj(proj.id, fd, {}, original_path=item_system_path)
                    os.remove(os.path.join("/tmp", tmp_file_uuid))
                else:
                    continue
            except ApiException as e:
                logger.exception(e)
                continue
            except Exception as e:
                logger.exception(e)
                continue



@app.task()
def refresh_observable_projects():
    obs = db_session.query(ObservableDataProject).all()
    for o in obs:
        import_from_agave(o.project.users[0], o.system_id, o.path, o.project)


if __name__ =="__main__":
    u = db_session.query(User).get(1)
    refresh_observable_projects()