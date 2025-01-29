# syntax = docker/dockerfile:1

## Uncomment the version of python you want to test against
# FROM python:3.9-alpine
# FROM python:3.10-alpine
# FROM python:3.11-alpine
# FROM python:3.12-alpine
FROM python:3.13-alpine
# FROM python:3.14-rc-alpine

# Set the working directory to /app
WORKDIR /app/

# Install deps needed for alpine to build cffi
RUN apk update && apk --no-cache add build-base libffi-dev

# Copy and install the requirements
# This includes egg installing the django_sockets package
COPY django_sockets/__init__.py /app/django_sockets/__init__.py
COPY pyproject.toml /app/pyproject.toml
RUN pip install -e .

COPY ./util_test_helper.sh /app/util_test_helper.sh
COPY ./test/01_basic_function.py /app/test/01_basic_function.py

CMD ["/bin/ash"]
# Comment out ENTRYPOINT to drop into an interactive shell for debugging when using test.sh
ENTRYPOINT ["/app/util_test_helper.sh"]
