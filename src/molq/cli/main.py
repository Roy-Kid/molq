#!/usr/bin/env python3
"""Molq CLI — submit, track, and manage jobs on local and HPC schedulers.

The Typer application lives in :mod:`molq.cli._app`; importing the command
modules here is what registers their commands on it.  ``molq.cli.main:app``
stays the console-script entry point.
"""

from __future__ import annotations

from molq.cli import jobs, maintenance, setup  # noqa: F401  (registers commands)
from molq.cli._app import app

__all__ = ["app"]


if __name__ == "__main__":
    app()
