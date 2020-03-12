
from flask import Flask
from geoapi.routes import api
from geoapi.settings import settings as app_settings
from geoapi.db import db_session
from geoapi.exceptions import InvalidGeoJSON, InvalidEXIFData, InvalidCoordinateReferenceSystem, ApiException

import logging

logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)


app = Flask(__name__)
api.init_app(app)
app.config.from_object(app_settings)

# api.errorhandler is needed as exceptions aren't being handled in flask-restplus 0.13 or 0.14
# (only seeing this in testing or dev server)
# See https://github.com/noirbizarre/flask-restplus/issues/744
@api.errorhandler(InvalidGeoJSON)
@app.errorhandler(InvalidGeoJSON)
def handle_geojson_exception(error: Exception):
    '''Return a custom message and 400 status code'''
    return ({
        "status": "error",
        "version": "0.1",
        "message": str(error)
    }, 400)

@api.errorhandler(ApiException)
@app.errorhandler(ApiException)
def handle_api_exception(error: Exception):
    '''Return a custom message and 400 status code'''
    return {
        "status": "error",
        "version": "0.1",
        "message": str(error)
    }, 400

@api.errorhandler(InvalidEXIFData)
@app.errorhandler(InvalidEXIFData)
def handle_exif_exception(error: Exception):
    '''Return a custom message and 400 status code'''
    return {'message': 'Invalid EXIF data, geolocation could not be found'}, 400

@api.errorhandler(InvalidCoordinateReferenceSystem)
@app.errorhandler(InvalidCoordinateReferenceSystem)
def handle_coordinate_reference_system_exception(error: Exception):
    return {'message': 'Invalid data, coordinate reference system could not be found'}, 400

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

