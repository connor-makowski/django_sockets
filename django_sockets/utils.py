import asyncio, logging, threading


logger = logging.getLogger(__name__)

# Django Channels Utils (To be importable from django_sockets)
# Do not remove these imports
from channels.routing import ProtocolTypeRouter, URLRouter


def run_in_thread(command, *args, **kwargs):
    """
    Takes in a synchronous command along with args and kwargs and runs it in a background
    thread that is not tied to the websocket connection.

    This will be terminated when the larger daphne server is terminated
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
    loop = loop if loop is not None else asyncio.get_event_loop()
    if not loop.is_running():
        try:
            thread = run_in_thread(start_event_loop_thread, loop)
        except:
            logger.log(logging.ERROR, "Event Loop already running")
    return loop
