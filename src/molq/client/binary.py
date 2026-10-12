"""Locate the serve executable. Configuration selects it; the environment does not."""

from __future__ import annotations

import json
import sys
from importlib.resources import files
from pathlib import Path

from molq.errors import MolqError


def executable(
    config: Path | str | None = None, override: Path | str | None = None
) -> str:
    """Return the molq binary path.

    Args:
        config: Optional configuration file whose client.executable field wins.
        override: Explicit constructor path. It wins over the configuration file.
    """
    if override:
        return str(override)
    if config:
        path = Path(config).expanduser()
        if path.is_file():
            try:
                data = json.loads(path.read_text())
            except (OSError, ValueError):
                data = {}
            chosen = data.get("client", {}).get("executable")
            if chosen:
                return str(Path(chosen).expanduser())
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "go.mod").is_file() and (parent / "bin" / "molq").is_file():
            return str(parent / "bin" / "molq")
    packaged = files("molq").joinpath(
        "_bin", "molq.exe" if sys.platform == "win32" else "molq"
    )
    if packaged.is_file():
        return str(packaged)
    raise MolqError("RUNTIME_UNAVAILABLE", "molq serve executable is not built")
