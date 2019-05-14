
from flask import Flask
from geoapi.routes import api
from geoapi.settings import settings as app_settings
from geoapi.db import db_session
from geoapi.exceptions import InvalidGeoJSON, InvalidEXIFData
import logging

logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)


app = Flask(__name__)
api.init_app(app)
app.config.from_object(app_settings)


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

@api.errorhandler(InvalidGeoJSON)
def handle_custom_exception(error):
    '''Return a custom message and 400 status code'''
    return {
        "status": "error",
        "version": "0.1",
        "message": 'Invalid GeoJSON. Valid input must be a Feature or FeatureCollection'
    }, 400

@api.errorhandler(InvalidEXIFData)
def handle_custom_exception(error):
    '''Return a custom message and 400 status code'''
    return {'message': 'Invalid EXIF data, geolocation could not be found'}, 400