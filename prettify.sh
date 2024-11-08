# Change to the script directory
cd $(dirname "$0")
# Lint and Autoformat the code in place
# Remove unused imports
autoflake --in-place --remove-all-unused-imports --ignore-init-module-imports -r ./django_sockets
# Perform all other steps
black --config pyproject.toml ./django_sockets
black --config pyproject.toml ./test
