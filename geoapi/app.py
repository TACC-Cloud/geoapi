
from flask import Flask
from flask_socketio import SocketIO
from geoapi.routes import api
from geoapi.settings import settings as app_settings
from geoapi.db import db_session
from geoapi.exceptions import (InvalidGeoJSON, InvalidEXIFData, InvalidCoordinateReferenceSystem,
                               ObservableProjectAlreadyExists, ApiException, StreetviewAuthException,
                               StreetviewLimitException)

import logging
from geoapi.utils.decorators import jwt_socket_decoder

logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)


app = Flask(__name__)
app.config.from_object(app_settings)


# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins='http://localhost:4200')
api.init_app(app)


@socketio.on('connect')
@jwt_socket_decoder
def handle_connect():
    logging.info('Client connected')


@socketio.on('trigger_notification')
def handle_notification(data):
    logging.info('Received trigger notification event: %s', data)
    # Emit a new notification with the message sent from the client
    # socketio.emit('new_notification', {'message': data.get('message')})
    # Otherwise, emit a default message
    socketio.emit('new_notification', {'message': 'This is a toast message!'})


@socketio.on('trigger_asset_success')
def handle_asset_success(data):
    logging.info('Received trigger notification event: %s', data)
    socketio.emit('asset_success', {'message': 'Asset was successfully added!'})


@socketio.on('trigger_asset_failure')
def handle_asset_failure(data):
    logging.info('Received trigger notification event: %s', data)
    socketio.emit('asset_failure', {'message': 'Asset failed to be added!'})


@socketio.on('client_message')
def handle_client_message(message):
    logging.info('Received message from client: %s', message)
    socketio.emit('server_message', {'message': 'This is a server message!'})


@socketio.on('disconnect')
def handle_disconnect():
    logging.info('Client disconnected')


@api.errorhandler(InvalidGeoJSON)
def handle_geojson_exception(error: Exception):
    '''Return a custom message and 400 status code'''
    return ({
        "status": "error",
        "version": "0.1",
        "message": str(error)
    }, 400)


@api.errorhandler(ApiException)
def handle_api_exception(error: Exception):
    '''Return a custom message and 400 status code'''
    return {
        "status": "error",
        "version": "0.1",
        "message": str(error)
    }, 400


@api.errorhandler(InvalidEXIFData)
def handle_exif_exception(error: Exception):
    '''Return a custom message and 400 status code'''
    return {'message': 'Invalid EXIF data, geolocation could not be found'}, 400


@api.errorhandler(InvalidCoordinateReferenceSystem)
def handle_coordinate_reference_system_exception(error: Exception):
    return {'message': 'Invalid data, coordinate reference system could not be found'}, 400


@api.errorhandler(ObservableProjectAlreadyExists)
def handle_observable_project_already_exists_exception(error: Exception):
    return {'message': 'Conflict, a project for this storage system/path already exists'}, 409


@api.errorhandler(StreetviewAuthException)
def handle_streetview_auth_exception(error: Exception):
    return {'message': 'Not logged in to streetview service'}, 401


@api.errorhandler(StreetviewLimitException)
def handle_streetview_limit_exception(error: Exception):
    return {'message': 'Exceed concurrent streetview publish limit'}, 403


# ensure SQLAlchemy sessions are properly closed at the end of each request.
@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


if __name__ == '__main__':
    socketio.run(app, port=8000, debug=True)
