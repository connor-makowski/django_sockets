#!/bin/bash
cd /app/
# Lint and Autoformat the code in place
# Remove unused imports
autoflake --in-place --ignore-init-module-imports -r ./django_sockets
# Perform all other steps
black --config pyproject.toml ./django_sockets
black --config pyproject.toml ./test
