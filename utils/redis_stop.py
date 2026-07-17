#!/usr/bin/env python
import subprocess


def stop_redis():
    container_name = "django_sockets_test_redis"
    print(
        f"Stopping and removing Valkey/Redis docker container '{container_name}'..."
    )
    subprocess.run(["docker", "stop", container_name], capture_output=True)
    subprocess.run(["docker", "rm", container_name], capture_output=True)
    print("Valkey/Redis container stopped and removed.")


if __name__ == "__main__":
    stop_redis()
