"""Run a simple shell command using the ``cmdline`` decorator."""

from molq import cmdline
from typing import Generator
import subprocess

@cmdline
def echo() -> Generator[dict, subprocess.CompletedProcess, str]:
    cp = yield {"cmd": ["echo", "hello"], "block": True}
    return cp.stdout.decode().strip()

if __name__ == "__main__":
    print(echo())
