from litestar import WebSocket, websocket
from litestar.channels import ChannelsPlugin
from geoapi.utils.decorators import not_anonymous_guard
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError
import logging

logger = logging.getLogger(__name__)


@websocket("/ws", guards=[not_anonymous_guard])
async def websocket_handler(socket: WebSocket, channels: ChannelsPlugin) -> None:
    await socket.accept()
    user = socket.scope.get("user")

    try:
        async with channels.start_subscription(
            [f"notifications-{user.id}"]
        ) as subscriber:
            async for message in subscriber.iter_events():
                try:
                    await socket.send_text(message)
                except (ConnectionClosedOK, ConnectionClosedError):
                    logger.debug(f"WebSocket closed for user {user.id}")
                    break
                except Exception:
                    logger.exception(f"WebSocket send error for user {user.id}")
                    break
    except Exception:
        logger.exception(f"WebSocket setup error for user {user.id}")
