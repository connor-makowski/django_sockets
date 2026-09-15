import asyncio, logging, binascii, msgpack, uuid
from redis.asyncio import Redis, ConnectionPool, sentinel
from redis.asyncio.cluster import RedisCluster

logger = logging.getLogger(__name__)


class PubSubLayer:
    """
    A meta PubSub Layer that uses Redis's pub/sub functionality and allows multiple subscriptions to
    different channels that may or may not be on different cache shards.

    This layer is designed to be used with asyncio and is not necessarily thread-safe.
    """

    def __init__(
        self,
        hosts=None,
    ):
        """
        Initialize the PubSub Layer

        Requires:
        - hosts: A list of dictionaries
            - Note: This uses a redis connection pool or a sentinel connection pool to connect to the Redis server.
            - Each dictionary should contain the following key value pairs (depending on the connection pool type):
                - ConnectionPool:
                    - address: The address of the Redis server
                        - EG: 'redis://0.0.0.0:6379'
                        - Note: This can be used alone or in conjunction with other connection pool keys
                    - host: The host of the Redis server
                        - Note: This must be used with the port key and can be used in conjunction with the other connection pool keys
                    - port: The port of the Redis server
                        - Note: This must be used with the host key and can be used in conjunction with the other connection pool keys
                    - Other keys listed in the redis-py ConnectionPool documentation
                - SentinelConnectionPool:
                    - master_name: The name of the master in a Redis Sentinel setup
                    - sentinels: A list of sentinel addresses
                    - sentinel_kwargs: A dictionary of keyword arguments to pass to the sentinel connect
                    - Other keys listed in the redis-py SentinelConnectionPool documentation
        """
        self.queue = asyncio.Queue()
        self.subscriptions = dict()
        if not isinstance(hosts, list):
            raise ValueError("Hosts must be a list of dictionaries")
        if len(hosts) == 0:
            raise ValueError("Hosts must contain at least one dictionary")
        self.shards = [ShardConnection(host, self) for host in hosts]

    # PubSub methods
    async def subscribe(self, channel: str):
        """
        Subscribe to a channel
        """
        shard = self.__get_shard__(channel)
        if channel not in self.subscriptions:
            self.subscriptions[channel] = shard
        await shard.subscribe(channel)

    async def unsubscribe(self, channel: str):
        """
        Unsubscribe from a channel
        """
        if channel in self.subscriptions:
            shard = self.subscriptions.pop(channel)
            await shard.unsubscribe(channel)

    async def send(self, channel: str, data):
        """
        Send data to a channel
        """
        shard = self.__get_shard__(channel)
        await shard.publish(channel, data)

    async def send_many(self, channels: list[str], data):
        """
        Send data to multiple channels efficiently using shard grouping and pipelining
        """
        if not channels:
            return
        shard_channels = dict()
        for channel in channels:
            shard = self.__get_shard__(channel)
            if shard not in shard_channels:
                shard_channels[shard] = []
            shard_channels[shard].append(channel)

        tasks = []
        for shard, chs in shard_channels.items():
            tasks.append(shard.publish_many(chs, data))
        await asyncio.gather(*tasks)

    async def receive(self) -> dict | None:
        """
        Get the next item from the queue. This will hang until an item is available.

        If the queue has been closed, cleanup and raise an exception to exit the calling task.

        Format:
        {
            'channel': str,
            'data': Any
        }
        """
        try:
            return await self.queue.get()
        except (asyncio.CancelledError, asyncio.TimeoutError, GeneratorExit):
            # Cleanup / unsubscribe on interruptions / exits / timeouts
            await self.flush()
            # Raise an exception to exit the calling task
            raise asyncio.CancelledError

    async def flush(self):
        """
        Flush the layer and close all connections across all shards.
        """
        for shard in self.shards:
            try:
                await shard.flush()
            except asyncio.CancelledError:
                raise asyncio.CancelledError
            except BaseException as e:
                logger.exception(
                    f"Exception while flushing shard connection: {e}"
                )
        self.subscriptions = dict()

    # Utility Methods
    def __get_shard__(self, channel):
        """
        Return the shard that is used for this channel.

        This is done by assigning a shard index location based on the CRC32 of the channel name.
        """
        if len(self.shards) == 1:
            shard_index = 0
        else:
            channel_bytes = str(channel).encode("utf-8")
            hash_val = binascii.crc32(channel_bytes) & 0xFFF
            shard_index = int(hash_val / (4096 / float(len(self.shards))))
        return self.shards[shard_index]


class ShardConnection:
    def __init__(self, host, pubsub_layer_obj, prefix="pubsub"):
        self.host = host.copy()
        self.is_cluster = bool(
            self.host.pop("is_cluster", False)
            or self.host.pop("cluster", False)
        )
        if not self.is_cluster:
            self.connection_pool = self.__get_connection_pool__(self.host)
        else:
            self.connection_pool = None
        self.pubsub_layer_obj = pubsub_layer_obj
        self.lock = asyncio.Lock()
        self.connection = None
        self.pubsub = None
        self.receiver_task = None
        self.subscriptions = set()
        self.prefix = prefix

    # PubSub methods
    async def subscribe(self, channel):
        channel = self.__get_channel_name__(channel)
        async with self.lock:
            if channel in self.subscriptions:
                return
            await self.__ensure_connection__(calling_fn="subscribe")
            await self.pubsub.subscribe(channel)
            self.subscriptions.add(channel)
        # Drop out of the lock to start the receiver task which requires the lock to be released
        await self.ensure_receiver_task()

    async def unsubscribe(self, channel):
        channel = self.__get_channel_name__(channel)
        async with self.lock:
            if channel not in self.subscriptions:
                return
            await self.__ensure_connection__(calling_fn="unsubscribe")
            await self.pubsub.unsubscribe(channel)
            self.subscriptions.remove(channel)
        if len(self.subscriptions) == 0:
            await self.flush()

    async def publish(self, channel, message):
        channel_name = self.__get_channel_name__(channel)
        # Serialize payload outside the connection lock to avoid blocking other concurrent publishes
        serialized_message = self.__serialize__(message)

        # If the message is larger than 1MB, save it in the cache with a 60s TTL and publish the key pointer
        if len(serialized_message) > 1024 * 1024:
            msg_loc_key = f"{self.prefix}.{str(uuid.uuid4())}"
            pointer_message = self.__serialize__(f"msg:{msg_loc_key}")
            async with self.lock:
                await self.__ensure_connection__(calling_fn="publish")
                await self.connection.set(
                    msg_loc_key, serialized_message, ex=60
                )
                await self.connection.publish(channel_name, pointer_message)
        else:
            async with self.lock:
                await self.__ensure_connection__(calling_fn="publish")
                await self.connection.publish(channel_name, serialized_message)

    async def publish_many(self, channels: list[str], message):
        if not channels:
            return
        serialized_message = self.__serialize__(message)

        if len(serialized_message) > 1024 * 1024:
            msg_loc_key = f"{self.prefix}.{str(uuid.uuid4())}"
            pointer_message = self.__serialize__(f"msg:{msg_loc_key}")
            async with self.lock:
                await self.__ensure_connection__(calling_fn="publish_many")
                await self.connection.set(
                    msg_loc_key, serialized_message, ex=60
                )
                pipe = self.connection.pipeline()
                for ch in channels:
                    pipe.publish(self.__get_channel_name__(ch), pointer_message)
                await pipe.execute()
        else:
            async with self.lock:
                await self.__ensure_connection__(calling_fn="publish_many")
                pipe = self.connection.pipeline()
                for ch in channels:
                    pipe.publish(
                        self.__get_channel_name__(ch),
                        serialized_message,
                    )
                await pipe.execute()

    async def ensure_receiver_task(self):
        async with self.lock:
            if self.receiver_task is None:
                self.receiver_task = asyncio.create_task(
                    self.__receiver_task__()
                )
                # This is needed to continue the main coroutine execution after create_task
                await asyncio.sleep(0)

    async def flush(self):
        # Flushing is not locked since it can be called from inside the lock
        if self.receiver_task and self.receiver_task != asyncio.current_task():
            self.receiver_task.cancel()
            try:
                await self.receiver_task
            except asyncio.CancelledError:
                pass
            self.receiver_task = None
        elif self.receiver_task == asyncio.current_task():
            self.receiver_task = None

        if self.pubsub:
            try:
                await self.pubsub.aclose()
            except Exception:
                pass
            self.pubsub = None
        if self.connection:
            try:
                await self.connection.aclose()
            except Exception:
                pass
            self.connection = None

    # Tasks
    async def __receiver_task__(self):
        """
        Start an event-driven task to receive messages from the pubsub and put them in the queue.

        Uses async generator `pubsub.listen()` backed by socket I/O rather than artificial polling sleep.
        """
        try:
            while len(self.subscriptions) > 0:
                try:
                    if not self.pubsub:
                        async with self.lock:
                            await self.__ensure_connection__(
                                calling_fn="receiver"
                            )
                            if self.subscriptions:
                                await self.pubsub.subscribe(*self.subscriptions)

                    async for message in self.pubsub.listen():
                        if not self.pubsub or len(self.subscriptions) == 0:
                            break
                        if message and message.get("type") == "message":
                            message_data = self.__deserialize__(message["data"])
                            # If the message was too large, get that message from the cache
                            if isinstance(
                                message_data, str
                            ) and message_data.startswith("msg:"):
                                msg_loc_key = message_data[4:]
                                if self.connection:
                                    raw_msg = await self.connection.get(
                                        msg_loc_key
                                    )
                                    if raw_msg is not None:
                                        message_data = self.__deserialize__(
                                            raw_msg
                                        )
                            raw_channel = message["channel"]
                            channel_name = (
                                raw_channel.decode("utf-8")
                                if isinstance(raw_channel, bytes)
                                else raw_channel
                            )
                            self.pubsub_layer_obj.queue.put_nowait(
                                {
                                    "channel": self.__get_channel_from_name__(
                                        channel_name
                                    ),
                                    "data": message_data,
                                }
                            )
                except (asyncio.CancelledError, GeneratorExit):
                    raise
                except Exception as e:
                    if len(self.subscriptions) == 0:
                        break
                    logger.warning(
                        f"Connection lost in pubsub receiver, attempting reconnect: {e}"
                    )
                    async with self.lock:
                        try:
                            await self.__ensure_connection__(
                                calling_fn="receiver_reconnect", force=True
                            )
                            if self.subscriptions:
                                await self.pubsub.subscribe(*self.subscriptions)
                        except Exception:
                            pass
                    await asyncio.sleep(0.5)
        except (asyncio.CancelledError, GeneratorExit):
            raise
        finally:
            await self.flush()

    # Utility Methods
    async def __ensure_connection__(self, calling_fn: str, force: bool = False):
        """
        Ensure that the connection to the cache is established.

        Note: This should only be called within a lock.
        """
        if force and self.connection:
            try:
                await self.connection.aclose()
            except Exception:
                pass
            self.connection = None
            self.pubsub = None

        if not self.connection:
            if self.is_cluster:
                host_cfg = self.host.copy()
                if "address" in host_cfg:
                    address = host_cfg.pop("address")
                    self.connection = RedisCluster.from_url(address, **host_cfg)
                else:
                    self.connection = RedisCluster(**host_cfg)
            else:
                self.connection = Redis(connection_pool=self.connection_pool)
            # If the connection failed, then raise an exception
            try:
                is_connected = await self.connection.ping()
            except Exception:
                is_connected = False
            if not is_connected:
                logger.log(
                    logging.ERROR,
                    f"Error: ({calling_fn}) Could not connect to the cache server. Consider trying:\n  - Ensuring that the cache server is running.\n  - Checking your config is correct.\n  - Checking that the cache server is reachable from this server.",
                )
                raise ConnectionError("Could not connect to the cache server.")
            self.pubsub = self.connection.pubsub()

    def __get_channel_name__(self, channel):
        """
        Get the channel name with the prefix.
        """
        return f"{self.prefix}.{channel}"

    def __get_channel_from_name__(self, channel_name):
        """
        Get the channel name without the prefix.
        """
        return channel_name[len(self.prefix) + 1 :]

    def __serialize__(self, message):
        """
        Serialize a message into bytes.
        """
        return msgpack.packb(message)

    def __deserialize__(self, message):
        """
        Deserialize a message from bytes.
        """
        return msgpack.unpackb(message, strict_map_key=False)

    @staticmethod
    def __get_connection_pool__(host: dict):
        """
        Get a connection pool from a host dictionary
        """
        host = host.copy()
        if "address" in host:
            address = host.pop("address")
            return ConnectionPool.from_url(address, **host)

        master_name = host.pop("master_name", None)
        if master_name is not None:
            sentinels = host.pop("sentinels")
            sentinel_kwargs = host.pop("sentinel_kwargs", None)
            return sentinel.SentinelConnectionPool(
                master_name,
                sentinel.Sentinel(sentinels, sentinel_kwargs=sentinel_kwargs),
                **host,
            )
        return ConnectionPool(**host)
