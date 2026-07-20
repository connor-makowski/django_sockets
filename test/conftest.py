import subprocess
import time
import os
import socket


def pytest_sessionstart(session):
    # If cache environment variables are already defined, skip automatic docker container management
    if "CACHE_HOST" in os.environ and "CACHE_PORT" in os.environ:
        return

    container_name = "django_sockets_test_redis"

    # Preemptively stop and remove any lingering/stopped container from previous sessions
    subprocess.run(["docker", "stop", container_name], capture_output=True)
    subprocess.run(["docker", "rm", container_name], capture_output=True)

    print(f"\nStarting Valkey docker container '{container_name}'...")
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "-p",
            "6379:6379",
            "--name",
            container_name,
            "valkey/valkey:7",
        ],
        check=True,
    )

    # Wait for Valkey to be ready to accept connections
    port_ready = False
    for _ in range(50):  # try for up to 5 seconds
        try:
            with socket.create_connection(("localhost", 6379), timeout=0.1):
                port_ready = True
                break
        except OSError:
            time.sleep(0.1)
    if not port_ready:
        raise RuntimeError(
            "Valkey/Redis container started but failed to accept connections on port 6379 within 5 seconds"
        )

    # Configure connection variables for the tests
    os.environ["CACHE_HOST"] = "localhost"
    os.environ["CACHE_PORT"] = "6379"


def pytest_sessionfinish(session, exitstatus):
    # If CACHE_HOST is not localhost, it means we probably didn't spin it up
    if os.environ.get("CACHE_HOST") != "localhost":
        return

    container_name = "django_sockets_test_redis"
    print(
        f"\nStopping and removing Valkey docker container '{container_name}'..."
    )
    subprocess.run(["docker", "stop", container_name], capture_output=True)
    subprocess.run(["docker", "rm", container_name], capture_output=True)
