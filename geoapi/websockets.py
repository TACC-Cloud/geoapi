from gevent import monkey

monkey.patch_all()

from flask_socketio import SocketIO
from geoapi.app import app
from geoapi.settings import settings as app_settings
from geoapi.utils.decorators import jwt_socket_decoder
from geoapi.log import logger
from geoapi.signals import create_notification


# Initialize SocketIO

socketio = SocketIO(
    app,
    cors_allowed_origins="http://localhost:4200",
    message_queue=f"redis://{app_settings.REDIS_HOSTNAME}:6379",
    logger=app_settings.DEBUG,
    engineio_logger=app_settings.DEBUG,
)


@socketio.on("connect")
@jwt_socket_decoder
def handle_connect():
    logger.info("Client connected")


@socketio.on("trigger_notification")
def handle_notification(data):
    """Handle a trigger notification event"""
    logger.info("Received trigger notification event: %s", data)
    # Emit a new notification with the message sent from the client
    # socketio.emit('new_notification', {'message': data.get('message')})
    # Otherwise, emit a default message
    socketio.emit("new_notification", {"message": "This is a toast message!"})


@socketio.on("trigger_asset_success")
def handle_asset_success(data):
    """Handle a trigger asset success event"""
    logger.info("Received trigger notification event: %s", data)
    socketio.emit("asset_success", {"message": "Asset was successfully added!"})


@socketio.on("trigger_asset_failure")
def handle_asset_failure(data):
    """Handle a trigger asset failure event"""
    logger.info("Received trigger notification event: %s", data)
    socketio.emit("asset_failure", {"message": "Asset failed to be added!"})


@socketio.on("client_message")
def handle_client_message(message):
    """Handle a client message event"""
    logger.info("Received message from client: %s", message)
    socketio.emit("server_message", {"message": "This is a server message!"})


@socketio.on("disconnect")
def handle_disconnect():
    """Handle a disconnect event"""
    logger.info("Client disconnected")


@socketio.on_error_default
def default_error_handler(e):
    """Handle default error"""
    logger.error("An error occurred: %s", e)


# Register Signals


def handle_create_notification(sender, **kwargs):
    """Handle a create notification signal"""
    logger.info("Received create notification signal")
    logger.debug("Caught signal from %s, data %s", sender, kwargs)
    socketio.emit("new_notification", **kwargs)


create_notification.connect(handle_create_notification)


if __name__ == "__main__":
    socketio.run(app, debug=app_settings.DEBUG)
