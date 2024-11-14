import asyncio, logging

from .pubsub import PubSubLayer
from .utils import ensure_loop_running

logger = logging.getLogger(__name__)


class Broadcaster:
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
    def broadcast(self, channel: str, data: [dict | list]):
        """
        Broadcast data to a specific channel or all channels that this socket server is subscribed to.

        Requires:

        - channel: str = The channel to broadcast the data to
        - data: [dict|list] = The data to broadcast to the channel
            - Note: This data must be JSON serializable
        """
        asyncio.run_coroutine_threadsafe(
            self.async_broadcast(channel, data), self.__loop__
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
    async def async_broadcast(self, channel: str, data):
        """
        Broadcast data to a channel where all relevant clients will receive the data
        and send it to the client

        Requires:

        - channel: str = The channel to broadcast the data to
        - data: [dict|list] = The data to broadcast to the channel
            - Note: This data must be JSON serializable
        """
        await self.pubsub_layer.send(str(channel), data)

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
