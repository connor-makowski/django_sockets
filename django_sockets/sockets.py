import orjson, asyncio, logging, inspect
from .broadcaster import Broadcaster

logger = logging.getLogger(__name__)


def __default_ws_encoder__(obj):
    """
    A default websocket encoder that uses orjson to serialize the data to a JSON string

    Required:

    - obj: [dict|list|str|float|int] = The data to serialize to a JSON string

    Returns:

    - str = The JSON string representation of the data
    """
    return orjson.dumps(obj).decode("utf-8")


class BaseSocketServer(Broadcaster):
    def __init__(
        self,
        scope,
        receive,
        send,
        hosts=[{"address": "redis://0.0.0.0:6379"}],
        ws_encoder=__default_ws_encoder__,
        ws_encoder_is_bytes=False,
    ):
        """
        Initialize the socket server

        Required:

        - scope: dict = The scope of the websocket connection
        - receive: method = The `get` method for an asyncio.Queue() object that will be used to receive data from the websocket client
        - send: async callable = The function that should send the data to the websocket client
            - Note: This function takes in a dictionary with the following keys:
                - type: str = The type of message to send (always 'websocket.send')
                - text: str = The data to send to the client (the json serialized version of the data sent / broadcasted)

        Optional:

        - hosts: list = A list of dictionaries that contain the host information for the socket server
            - See the PubSubLayer docs for more comprehensive docs on the hosts parameter
        - ws_encoder: callable = The function that will be used to encode messages sent to the websocket client
        - ws_encoder_is_bytes: bool = Whether or not the ws_encoder function returns bytes
        """
        self.scope = scope
        self.__receive__ = receive
        self.__send__ = send
        self.__send_lock__ = asyncio.Lock()
        self.is_alive = True
        self.hosts = hosts
        self.ws_encoder = ws_encoder
        self.ws_encoder_is_bytes = ws_encoder_is_bytes
        self.configure()
        super().__init__(hosts=self.hosts)

        # Cache method inspection checks to avoid per-message inspection overhead
        self._is_async_receive = inspect.iscoroutinefunction(self.receive)
        self._is_async_connect = inspect.iscoroutinefunction(self.connect)
        self._is_async_disconnect = inspect.iscoroutinefunction(self.disconnect)
        try:
            sig = inspect.signature(self.disconnect)
            self._disconnect_has_params = len(sig.parameters) > 0
        except Exception:
            self._disconnect_has_params = True

    def configure(self):
        """
        Callable that allows the socket server to be configured when launched from the ASGI application

        This is a placeholder method that can be overwritten by the user to configure the socket server.

        This method will be called during socket server initialization and any variables set here will take precedence over
        passed variables during initialization.

        This method should be used to configure:

        - self.hosts: list = A list of dictionaries that contain the host information for the socket server
            - See the PubSubLayer docs for more comprehensive docs on the hosts parameter
        - self.ws_encoder: callable = The function that will be used to encode messages sent to the websocket client
        - self.ws_encoder_is_bytes: bool = Whether or not the ws_encoder function returns bytes
        """

    # Sync Functions
    def send(
        self, data: [dict | list | str | float | int | bytes], raw: bool = False
    ):
        """
        Send data to the websocket client.
        - Note: This only sends data to the client from which the calling function was called
        - Note: To send data to all clients that are subscribed to a channel, use the broadcast method
                which is inherited from the Broadcaster class

        Requires:

        - data: [dict|list|str|float|int|bytes] = The data to send to the client
        - raw: bool = If True, bypasses ws_encoder and sends raw string/bytes directly
        """
        self.run_async(self.async_send(data, raw=raw))

    def close(self, code: int = 1000):
        """
        Close the websocket connection from the server side.

        Requires:
        - code: int = The WebSocket close code (default: 1000)
        """
        self.run_async(self.async_close(code=code))

    def run_async(self, func):
        """
        Run an async function in the current object's event loop
        """
        try:
            loop = asyncio.get_running_loop()
            if loop is self.__loop__:
                return loop.create_task(func)
        except RuntimeError:
            pass
        return asyncio.run_coroutine_threadsafe(func, self.__loop__)

    # Async Functions
    async def async_send(
        self, data: [dict | list | str | float | int | bytes], raw: bool = False
    ):
        """
        Send data to the websocket client.
        - Note: To send data to all clients that are subscribed to a channel, use the broadcast method
                which is inherited from the Broadcaster class

        Requires:

        - data: [dict|list|str|float|int|bytes] = The data to send to the client
        - raw: bool = If True, bypasses ws_encoder and sends raw string/bytes directly
        """
        if self.__send__ is None:
            logger.log(
                logging.ERROR,
                "The send and async_send functions are not available because the send parameter was not provided when the socket server was initialized. To silence this warning, you can provide a function that simulates some sending behavior.",
            )
            return

        try:
            if raw:
                encoded_data = data
                encoded_type = (
                    "bytes" if isinstance(data, (bytes, bytearray)) else "text"
                )
            else:
                encoded_data = self.ws_encoder(data)
                encoded_type = (
                    "bytes"
                    if (
                        self.ws_encoder_is_bytes
                        or isinstance(encoded_data, (bytes, bytearray))
                    )
                    else "text"
                )
            async with self.__send_lock__:
                await self.__send__(
                    {"type": "websocket.send", encoded_type: encoded_data}
                )
        except Exception as e:
            if self.is_alive:
                logger.log(logging.ERROR, f"Error during socket send: {e}")

    async def async_close(self, code: int = 1000):
        """
        Close the websocket connection from the server side asynchronously.

        Requires:
        - code: int = The WebSocket close code (default: 1000)
        """
        self.__kill__()
        if self.__send__ is not None:
            try:
                async with self.__send_lock__:
                    await self.__send__(
                        {"type": "websocket.close", "code": code}
                    )
            except Exception as e:
                logger.log(logging.ERROR, f"Error during socket close: {e}")

    async def async_handle_received_broadcast(
        self, channel: str, data: [dict | list | str | float | int]
    ):
        """
        Handle a received broadcast from a subscribed channel

        This method is provided so that it can be overwritten by the user if they want to handle
        received broadcasts from subscriptions in a specific way.

        By default, this method will send the data to the client using the async_send method

        In general, this method should only be called by the __broadcast_listener_task__ method

        Requires:

        - channel: str = The channel that the data was broadcasted to
        - data: [dict|list|str|float|int] = The data that was broadcasted
            - Note: This data must be JSON serializable
        """
        await self.async_send(data)

    async def _dispatch_receive(self, data_payload):
        try:
            if self._is_async_receive:
                await self.receive(data_payload)
            else:
                await asyncio.to_thread(self.receive, data_payload)
        except Exception:
            logger.exception("Exception in receive handler")

    # Tasks
    async def __ws_listener_task__(self):
        """
        Listen for incoming WS data and handle it accordingly
        """
        if self.__receive__ is None:
            logger.log(
                logging.ERROR,
                "The websocket listener task is not available because the receive parameter was not provided when the socket server was initialized. To silence this warning, you can provide an asyncio.Queue() receive parameter and put items in it to simulate received ws messages.",
            )
        else:
            while self.is_alive:
                data = await self.__receive__()
                if data["type"] == "websocket.receive":
                    try:
                        raw_text = data.get("text")
                        if raw_text is not None:
                            data_payload = (
                                self.ws_decoder(raw_text)
                                if hasattr(self, "ws_decoder")
                                and callable(self.ws_decoder)
                                else orjson.loads(raw_text)
                            )
                        elif "bytes" in data:
                            data_payload = (
                                self.ws_decoder(data["bytes"])
                                if hasattr(self, "ws_decoder")
                                and callable(self.ws_decoder)
                                else orjson.loads(data["bytes"])
                            )
                        else:
                            data_payload = data

                        asyncio.create_task(
                            self._dispatch_receive(data_payload)
                        )
                    except Exception:
                        logger.exception("Invalid WS data received")
                elif data["type"] == "websocket.disconnect":
                    self.__kill__()
                    code = data.get("code", 1000)
                    if self._is_async_disconnect:
                        if self._disconnect_has_params:
                            await self.disconnect(code)
                        else:
                            await self.disconnect()
                    else:
                        if self._disconnect_has_params:
                            self.disconnect(code)
                        else:
                            self.disconnect()
                elif data["type"] == "websocket.connect":
                    resp = {"type": "websocket.accept"}
                    if self.scope.get("__chosen_subprotocol__"):
                        resp["subprotocol"] = self.scope.get(
                            "__chosen_subprotocol__"
                        )
                    elif hasattr(self, "subprotocol") and self.subprotocol:
                        resp["subprotocol"] = self.subprotocol
                    async with self.__send_lock__:
                        await self.__send__(resp)
                    if self._is_async_connect:
                        await self.connect()
                    else:
                        self.connect()
                else:
                    raise ValueError(f"Invalid WS data type: {data['type']}")

    async def __broadcast_listener_task__(self):
        """
        Handle all messages that were broadcast to subscribed channels
        """
        # Only handle broadcasts if the broadcaster is usable
        while self.is_alive:
            try:
                channel, data = await self.async_receive_broadcast()
                await self.async_handle_received_broadcast(channel, data)
            # Cleanup on exit
            except asyncio.CancelledError:
                raise asyncio.CancelledError
            except Exception as e:
                raise e

    # Lifecycle Methods
    def __kill__(self):
        """
        Kill the socket server and stop all tasks
        """
        self.is_alive = False

    async def async_start_listeners(self):
        try:
            # Create Tasks for the listener and queue processor
            ws_listener_task = asyncio.create_task(self.__ws_listener_task__())
            broadcast_listener_task = asyncio.create_task(
                self.__broadcast_listener_task__()
            )
            # Wait until the socket server is killed or the tasks are cancelled
            while self.is_alive:
                await asyncio.sleep(0.05)
        # Catch exits handled by Daphne and allow the tasks to be cancelled
        except asyncio.CancelledError:
            pass
        finally:
            # Ensure all tasks are cancelled
            ws_listener_task.cancel()
            broadcast_listener_task.cancel()
            # Allow the cancellation to run in the background
            await asyncio.sleep(0)

    def start_listeners(self):
        """
        Start the listeners for the socket server
        """
        self.run_async(self.async_start_listeners())

    # Utility Methods
    @classmethod
    async def as_asgi(cls, scope, receive, send):
        """
        An ASGI application runner function that can be called by Daphne.

        This creates a new socket server instance and starts the listeners in the background.
        """
        # Wrap in a try / except block to catch unclean exits handled by Daphne
        socket_server = cls(scope, receive, send)
        await socket_server.async_start_listeners()

    # Placeholder Methods
    def receive(self, data):
        """
        Placeholder method for the receive method that must be overwritten by the user

        This is the method that will be called when data is received from the ws client.
        """
        raise NotImplementedError(
            "The receive method must be implemented by the user"
        )

    def connect(self):
        """
        Placeholder method for the connect method that can be overwritten by the user.
        """

    def disconnect(self, code):
        """
        Placeholder method for the disconnect method that can be overwritten by the user.
        """
