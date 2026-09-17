import asyncio, logging, threading

logger = logging.getLogger(__name__)


_LOOP_START_LOCK = threading.Lock()


class ProtocolTypeRouter:
    """
    ASGI application router that routes incoming connections based on scope type
    (e.g., 'http', 'websocket', or 'lifespan').
    """

    __slots__ = ("application_mapping",)

    def __init__(self, application_mapping):
        """
        Initialize the ProtocolTypeRouter

        Requires:

        - application_mapping: dict = Mapping of ASGI scope types (str) to ASGI applications
        """
        self.application_mapping = application_mapping

    async def __call__(self, scope, receive, send):
        scope_type = scope["type"]
        if scope_type in self.application_mapping:
            application = self.application_mapping[scope_type]
            return await application(scope, receive, send)
        if scope_type == "lifespan":
            try:
                while True:
                    message = await receive()
                    if message["type"] == "lifespan.startup":
                        await send({"type": "lifespan.startup.complete"})
                    elif message["type"] == "lifespan.shutdown":
                        await send({"type": "lifespan.shutdown.complete"})
                        return
            except asyncio.CancelledError:
                return
        raise ValueError(
            f"No application configured for protocol: {scope_type}"
        )


class URLRouter:
    """
    ASGI application router that routes WebSocket requests based on URL path patterns.
    Automatically handles path matching with or without trailing slashes.
    """

    __slots__ = ("routes",)

    def __init__(self, routes):
        """
        Initialize the URLRouter

        Requires:

        - routes: list = List of Django URL path patterns (e.g., `path("ws/", App.as_asgi)`)
        """
        self.routes = routes

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if path.startswith("/"):
            path = path[1:]
        for route in self.routes:
            match = route.pattern.match(path)
            if match is None and not path.endswith("/"):
                match = route.pattern.match(path + "/")
            if match is not None:
                remaining_path, args, kwargs = match
                new_scope = dict(scope)
                new_scope["url_route"] = {
                    "args": args,
                    "kwargs": kwargs,
                }
                return await route.callback(new_scope, receive, send)
        raise ValueError(f"No route found for path: /{path}")


def run_in_thread(command, *args, **kwargs):
    """
    Takes in a synchronous command along with args and kwargs and runs it in a background
    thread that is not tied to the websocket connection.

    This will be terminated when the larger server is terminated
    """
    thread = threading.Thread(
        target=command, args=args, kwargs=kwargs, daemon=True
    )
    thread.start()
    return thread


def start_event_loop_thread(loop):
    """
    Starts the event loop in a new thread
    """
    asyncio.set_event_loop(loop)
    loop.run_forever()


def ensure_loop_running(loop=None):
    """
    Starts the event loop in a new thread if not already running and returns the loop
    """
    if loop is None or loop.is_closed():
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    if not loop.is_running():
        with _LOOP_START_LOCK:
            if not loop.is_running():
                try:
                    run_in_thread(start_event_loop_thread, loop)
                except Exception:
                    logger.log(logging.ERROR, "Event Loop already running")
    return loop
