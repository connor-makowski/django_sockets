#!/bin/bash

# Creating a Docker network
printf "Creating a Docker network..."
docker network create "django_sockets_network" > /dev/null
printf "done.\n"

# Start a redis server on the network
printf "Starting the redis server..."
docker run -d \
    --network "django_sockets_network" \
    --name django_sockets_cache valkey/valkey:7 \
    > /dev/null
printf "done.\n"


docker build . --tag "django_sockets" --quiet > /dev/null
# if an arg was passed: use it as an entrypoint
if [ -z "$1" ]; then
    docker run -it --rm \
        --volume "$(pwd):/app" \
        --network "django_sockets_network" \
        -e "CACHE_HOST=django_sockets_cache" \
        -e "CACHE_PORT=6379" \
        "django_sockets"
else
    docker run -it --rm \
        --volume "$(pwd):/app" \
        --network "django_sockets_network" \
        -e "CACHE_HOST=django_sockets_cache" \
        -e "CACHE_PORT=6379" \
        --entrypoint "/app/utils/$1.sh" \
        "django_sockets"
fi

printf "Cleaning up containers..."
docker rm --force "django_sockets_cache" "django_sockets" 2&> /dev/null
docker network rm "django_sockets_network" > /dev/null
printf "done.\n"