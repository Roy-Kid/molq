"""Build the platform serve binary into the Python package."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.dist import Distribution

ROOT = Path(__file__).resolve().parent


def build_binary() -> None:
    """Compile the current platform binary. Users do not need a Go toolchain."""
    destination = ROOT / "src" / "molq" / "_bin"
    destination.mkdir(parents=True, exist_ok=True)
    name = "molq.exe" if os.name == "nt" else "molq"
    env = os.environ.copy()
    env["CGO_ENABLED"] = "0"
    subprocess.check_call(
        ["go", "build", "-o", str(destination / name), "./cmd/molq"], cwd=ROOT, env=env
    )


class BuildPy(build_py):
    """Place the serve executable in package data before copying sources."""

    def run(self) -> None:
        build_binary()
        super().run()


class BinaryDistribution(Distribution):
    """Mark the wheel as platform-specific because it contains the serve binary."""

    def has_ext_modules(self) -> bool:
        return True


setup(cmdclass={"build_py": BuildPy}, distclass=BinaryDistribution)
