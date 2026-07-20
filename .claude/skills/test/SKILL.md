---
name: test
description: Run the django_sockets test suite via uv run nox (all supported Python versions) or uv run pytest (local venv). Use when asked to run tests, verify changes, or check CI-equivalent behavior.
---

# Running Tests

| Command | What it does |
|---|---|
| `uv run nox` | Run tests across Python 3.11, 3.12, 3.13, 3.14 |
| `uv run pytest` | Run tests in the local venv only |
| `uv run pytest -v` | Run tests with verbose output |

For testing, you will need to run `uv sync --extra dev` after making any dependency changes. This installs development tools (`pytest`, `nox`, `black`, `autoflake`, etc.) into your local virtual environment.

Prefer `uv run pytest` for a quick local check while iterating; use `uv run nox` before considering a change done, since it confirms behavior across every Python version the package supports.
