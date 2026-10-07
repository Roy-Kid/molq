"""Async process/file I/O, orthogonal to Scheduler semantics."""

from __future__ import annotations

import asyncio
import os
import shlex
import signal
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from molq.errors import MolqError

OUTPUT_LIMIT = 1048576


@dataclass(frozen=True)
class Result:
    """Bounded command result."""

    returncode: int
    stdout: bytes
    stderr: bytes

    @property
    def text(self) -> str:
        """Decode command text without treating stderr as structured state."""
        return self.stdout.decode("utf-8", "replace")


class Transport(Protocol):
    """Target I/O with deadlines and cancellation; no scheduler knowledge."""

    async def run(
        self, argv: list[str], *, timeout: float = 30, input: bytes | None = None
    ) -> Result: ...
    async def read(
        self, path: str, *, offset: int = 0, limit: int = 262144
    ) -> bytes: ...
    async def write(
        self, path: str, data: bytes, *, offset: int | None = None
    ) -> None: ...


async def _bounded(stream: asyncio.StreamReader | None) -> bytes:
    assert stream is not None
    data = bytearray()
    while chunk := await stream.read(65536):
        data.extend(chunk)
        if len(data) > OUTPUT_LIMIT:
            raise MolqError(
                "TRANSPORT_UNAVAILABLE", "Command output exceeds bounded frame size"
            )
    return bytes(data)


class LocalTransport:
    """Use native asynchronous subprocesses, without shell=True."""

    async def run(
        self, argv: list[str], *, timeout: float = 30, input: bytes | None = None
    ) -> Result:
        """Run a finite helper and reap it on timeout/cancellation."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                start_new_session=os.name != "nt",
                stdin=asyncio.subprocess.PIPE
                if input is not None
                else asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise MolqError(
                "TRANSPORT_UNAVAILABLE",
                "Cannot start target command",
                command=argv[0],
                dispatched=False,
            ) from exc
        tasks = [
            asyncio.create_task(_bounded(proc.stdout)),
            asyncio.create_task(_bounded(proc.stderr)),
        ]

        async def feed():
            if proc.stdin is not None:
                proc.stdin.write(input or b"")
                try:
                    await proc.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                proc.stdin.close()
            await proc.wait()

        tasks.append(asyncio.create_task(feed()))
        try:
            async with asyncio.timeout(timeout):
                results = await asyncio.gather(*tasks)
            return Result(proc.returncode or 0, results[0], results[1])
        except (TimeoutError, asyncio.CancelledError, MolqError) as exc:
            if os.name != "nt":
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif proc.returncode is None:
                proc.kill()
            await proc.wait()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            if isinstance(exc, TimeoutError):
                raise MolqError(
                    "TRANSPORT_UNAVAILABLE",
                    "Target command deadline exceeded",
                    command=argv[0],
                ) from exc
            raise

    async def read(self, path: str, *, offset: int = 0, limit: int = 262144) -> bytes:
        """Read one bounded local file chunk."""
        try:
            with open(path, "rb") as f:
                f.seek(offset)
                return f.read(limit)
        except OSError as exc:
            raise MolqError(
                "FILE_UNAVAILABLE", "Cannot read target file", path=path
            ) from exc

    async def write(self, path: str, data: bytes, *, offset: int | None = None) -> None:
        """Atomically replace a file or write a bounded chunk."""
        import uuid

        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            if offset is None:
                temp = p.with_name(p.name + "." + uuid.uuid4().hex + ".tmp")
                try:
                    with temp.open("xb") as f:
                        f.write(data)
                    temp.chmod(0o600)
                    temp.replace(p)
                finally:
                    temp.unlink(missing_ok=True)
            else:
                with p.open("r+b" if p.exists() else "w+b") as f:
                    f.seek(offset)
                    f.write(data)
        except OSError as exc:
            raise MolqError(
                "FILE_UNAVAILABLE", "Cannot write target file", path=path
            ) from exc


class SshTransport:
    """Invoke system OpenSSH; configuration and mux remain OpenSSH-owned."""

    def __init__(self, alias: str):
        self.alias = alias
        self.local = LocalTransport()

    async def run(
        self, argv: list[str], *, timeout: float = 30, input: bytes | None = None
    ) -> Result:
        """Quote one remote argv without replacing OpenSSH connection options."""
        return await self.local.run(
            ["ssh", "-T", "-o", "BatchMode=yes", "--", self.alias, shlex.join(argv)],
            timeout=timeout,
            input=input,
        )

    async def read(self, path: str, *, offset: int = 0, limit: int = 262144) -> bytes:
        """Read one bounded remote chunk using standard target file tools."""
        result = await self.run(
            ["dd", f"if={path}", "bs=1", f"skip={offset}", f"count={limit}"]
        )
        if result.returncode:
            raise MolqError(
                "FILE_UNAVAILABLE", "Cannot read remote target file", path=path
            )
        return result.stdout

    async def write(self, path: str, data: bytes, *, offset: int | None = None) -> None:
        """Write remote stdin, with atomic replacement for staged scripts."""
        import posixpath
        import uuid

        q = shlex.quote
        parent = posixpath.dirname(path)
        temp = path + "." + uuid.uuid4().hex + ".tmp"
        if offset is None:
            script = f"umask 077; mkdir -p -- {q(parent)} && cat > {q(temp)} && mv -f -- {q(temp)} {q(path)}"
        else:
            script = f"umask 077; mkdir -p -- {q(parent)} && dd of={q(path)} bs=1 seek={offset} conv=notrunc"
        result = await self.run(["sh", "-c", script], input=data)
        if result.returncode:
            raise MolqError(
                "FILE_UNAVAILABLE", "Cannot write remote target file", path=path
            )


def create_transport(definition: dict) -> Transport:
    """Assemble the explicitly configured transport without guessing aliases."""
    return (
        SshTransport(definition["alias"])
        if definition["kind"] == "ssh"
        else LocalTransport()
    )
