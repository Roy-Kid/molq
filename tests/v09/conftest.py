"""Fresh owned state and strict native fixtures for 0.9 contracts."""

import asyncio

import pytest

from molq.runtime import Runtime
from molq.runtime.planning import normalize
from molq.transport import Result


class FakeTransport:
    def __init__(self, responses=()):
        self.responses = list(responses)
        self.calls = []
        self.files = {}

    async def run(self, argv, *, timeout=30, input=None):
        self.calls.append((argv, timeout, input))
        if not self.responses:
            return Result(0, b"", b"")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return (
            Result(0, response.encode(), b"") if isinstance(response, str) else response
        )

    async def read(self, path, *, offset=0, limit=262144):
        return self.files[path][offset : offset + limit]

    async def write(self, path, data, *, offset=None):
        self.files[path] = (
            data if offset is None else self.files.get(path, b"")[:offset] + data
        )


@pytest.fixture
def runtime(tmp_path):
    runtime = Runtime(tmp_path / "registry.db")
    yield runtime
    asyncio.run(runtime.close())


@pytest.fixture
def spec():
    return normalize(
        {
            "execution": {
                "units": [
                    {"id": "main", "command": {"kind": "argv", "argv": ["echo", "ok"]}}
                ]
            }
        },
        {},
    )
