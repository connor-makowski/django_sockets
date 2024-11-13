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

# Lint and Autoformat the code in place
# Remove unused imports
python -m autoflake --in-place --remove-all-unused-imports --ignore-init-module-imports -r ./django_sockets
# Perform all other steps
python -m black --config pyproject.toml ./django_sockets
python -m black --config pyproject.toml ./test
