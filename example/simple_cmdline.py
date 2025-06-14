"""Run a simple shell command using the ``cmdline`` decorator."""

from molq import cmdline

@cmdline
def echo() -> str:
    cp = yield {"cmd": "echo hello", "block": True}
    return cp.stdout.decode().strip()

if __name__ == "__main__":
    print(echo())
