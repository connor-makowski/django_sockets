import asyncio, logging, threading

logger = logging.getLogger(__name__)


class ProtocolTypeRouter:
    def __init__(self, application_mapping):
        self.application_mapping = application_mapping

    async def __call__(self, scope, receive, send):
        scope_type = scope["type"]
        if scope_type in self.application_mapping:
            application = self.application_mapping[scope_type]
            return await application(scope, receive, send)
        if scope_type == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        raise ValueError(
            f"No application configured for protocol: {scope_type}"
        )


class URLRouter:
    def __init__(self, routes):
        self.routes = routes

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if path.startswith("/"):
            path = path[1:]
        for route in self.routes:
            match = route.pattern.match(path)
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
    Starts the event loop in a new thread and returns the thread
    """
    if loop is None or loop.is_closed():
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Default loop is closed")
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    if not loop.is_running():
        try:
            thread = run_in_thread(start_event_loop_thread, loop)
        except:
            logger.log(logging.ERROR, "Event Loop already running")
    return loop
