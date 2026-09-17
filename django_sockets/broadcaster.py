import asyncio, logging

from .pubsub import PubSubLayer
from .utils import ensure_loop_running

logger = logging.getLogger(__name__)


class Broadcaster:
    __slots__ = ("__loop__", "pubsub_layer")

    def __init__(
        self,
        *args,
        loop=None,
        hosts=[{"address": "redis://0.0.0.0:6379"}],
        **kwargs,
    ):
        self.__loop__ = ensure_loop_running(loop)
        self.pubsub_layer = PubSubLayer(hosts=hosts)

    # Sync Functions
    def broadcast(self, channel: str | list[str] | tuple, data: [dict | list]):
        """
        Broadcast data to a specific channel, list of channels, or all channels that this socket server is subscribed to.

        Requires:

        - channel: [str|list|tuple] = The channel or channels to broadcast the data to
        - data: [dict|list] = The data to broadcast to the channel
            - Note: This data must be JSON serializable
        """
        asyncio.run_coroutine_threadsafe(
            self.async_broadcast(channel, data), self.__loop__
        )

    def broadcast_many(self, channels: list[str], data: [dict | list]):
        """
        Broadcast data to multiple channels.

        Requires:

        - channels: list[str] = List of channel names to broadcast the data to
        - data: [dict|list] = The data to broadcast
        """
        asyncio.run_coroutine_threadsafe(
            self.async_broadcast_many(channels, data), self.__loop__
        )

    def subscribe(self, channel: str):
        """
        Subscribe to a channel to receive data from broadcasts

        Requires:

        - channel: str = The channel to subscribe to
        """
        asyncio.run_coroutine_threadsafe(
            self.async_subscribe(channel), self.__loop__
        )

    # Async Functions
    async def async_broadcast(self, channel: str | list[str] | tuple, data):
        """
        Broadcast data to a channel or channels where all relevant clients will receive the data
        and send it to the client

        Requires:

        - channel: [str|list|tuple] = The channel or channels to broadcast the data to
        - data: [dict|list] = The data to broadcast to the channel
            - Note: This data must be JSON serializable
        """
        if isinstance(channel, str):
            await self.pubsub_layer.send(channel, data)
        elif isinstance(channel, (list, tuple, set)):
            await self.async_broadcast_many(list(channel), data)
        else:
            await self.pubsub_layer.send(str(channel), data)

    async def async_broadcast_many(self, channels: list[str], data):
        """
        Broadcast data to multiple channels asynchronously.

        Requires:

        - channels: list[str] = List of channels to broadcast the data to
        - data: [dict|list] = The data to broadcast
        """
        await self.pubsub_layer.send_many(list(channels), data)

    async def async_subscribe(self, channel: str):
        """
        Subscribe to a channel to receive data from broadcasts

        Requires:

        - channel: str = The channel to subscribe to
        """
        await self.pubsub_layer.subscribe(str(channel))

    async def async_receive_broadcast(self):
        """
        Receive a broadcast from a channel that this socket server is subscribed to

        Returns:

        - channel: str = The channel that the data was broadcasted to
        - data: [dict|list] = The data that was broadcasted to the channel
            - Note: This data must be JSON serializable
        """
        data = await self.pubsub_layer.receive()
        return data["channel"], data["data"]
