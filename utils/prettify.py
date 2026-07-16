#!/usr/bin/env python
import subprocess
import sys
from pathlib import Path

root = Path(__file__).parent.parent

subprocess.run(
    [
        sys.executable, "-m", "autoflake",
        "--in-place",
        "--ignore-init-module-imports",
        "-r",
        str(root / "django_sockets"),
    ],
    check=True,
)
subprocess.run(
    [sys.executable, "-m", "black", "--config", str(root / "pyproject.toml"), str(root / "django_sockets")],
    check=True,
)
subprocess.run(
    [sys.executable, "-m", "black", "--config", str(root / "pyproject.toml"), str(root / "test")],
    check=True,
)
