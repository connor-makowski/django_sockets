#!/usr/bin/env python
import subprocess
import time
import socket


def start_redis():
    container_name = "django_sockets_test_redis"

    # Preemptively stop and remove any lingering/stopped container
    subprocess.run(["docker", "stop", container_name], capture_output=True)
    subprocess.run(["docker", "rm", container_name], capture_output=True)

    print(f"Starting Valkey/Redis docker container '{container_name}'...")
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

    # Wait for Valkey/Redis to be ready to accept connections
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
    print("Valkey/Redis container is ready on port 6379.")


if __name__ == "__main__":
    start_redis()
