# Change to the script directory
cd $(dirname "$0")
# Ensure a properly setup virtual environment
printf "Setting up the virtual environment..."
python3 -m virtualenv venv > /dev/null
source venv/bin/activate
# If not in an venv, do not continue
if [ -z "$VIRTUAL_ENV" ]; then
    printf "\nNot in a virtual environment. Exiting."
    exit 1
fi
pip install -r requirements.txt > /dev/null
printf "done.\n"

# Start the redis server
printf "Starting the redis server..."
docker run -d -p 6379:6379 --name django_sockets_cache valkey/valkey:7 2> /dev/null
docker start django_sockets_cache > /dev/null
printf "done.\n"

# Run the tests
for f in test/*.py; do python "$f"; done

# Stop the redis server
docker kill django_sockets_cache > /dev/null
