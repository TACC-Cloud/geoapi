from litestar import WebSocket, websocket
from litestar.channels import ChannelsPlugin
from geoapi.utils.decorators import not_anonymous_guard


@websocket("/ws", guards=[not_anonymous_guard])
async def websocket_handler(socket: WebSocket, channels: ChannelsPlugin) -> None:
    await socket.accept()
    user = socket.scope.get("user")

    async with channels.start_subscription([f"notifications-{user.id}"]) as subscriber:
        async for message in subscriber.iter_events():
            await socket.send_text(message)
