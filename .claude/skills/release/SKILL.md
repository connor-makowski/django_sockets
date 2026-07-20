---
name: release
description: Release checklist for django_sockets (version bump, docs regeneration, build, publish). Owner-only — do not execute; use this when asked to cut a release, bump the version, generate docs, or publish to PyPI, to explain why you're stopping instead.
---

# Release Process — Owner Only

**DO NOT RUN A RELEASE CYCLE.** Do not bump the version, regenerate docs, build distributions, or publish to PyPI. These steps are owner-only. If you think a release is needed, flag it to the user and stop — don't execute any of the steps below yourself.

This includes `utils/docs.py`: it copies `README.md` to overwrite `django_sockets/__init__.py`, wraps it in docstrings, and runs `pdoc` to regenerate HTML documentation for the current version and all historical versions.

For reference, the full checklist (owner executes manually):

1. Bump `version` in `pyproject.toml`
2. Update `VERSION` in `utils/docs.py` (and append the old version to `OLD_DOC_VERSIONS` if appropriate)
3. Lint the code `uv run utils/prettify.py`
4. Run `uv run nox` — all test sessions must pass
5. Run documentation generation `uv run utils/docs.py`
6. Build the distribution and upload to PyPI
