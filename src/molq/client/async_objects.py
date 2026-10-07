"""Generated async OOP projection; edit objects.py and regenerate."""

from __future__ import annotations

import asyncio
import builtins
import time
from pathlib import Path
from typing import Any

from molq.client.async_wire import AsyncWire
from molq.domain import Execution, ExecutionUnit, JobSpec, Value
from molq.errors import MolqError


def wire_value(value: Any) -> Any:
    """Convert local value constructors, without schema interpretation."""
    return value.to_wire() if isinstance(value, Value) else value


class AsyncMolq:
    """Connect to one Runtime; absent endpoint uses its temporary stdio form.

    Args:
        endpoint: Explicit HTTP(S) endpoint, or MOLQ_ENDPOINT.
        registry: Registry path for a no-service stdio session.
        token: Endpoint credential, or MOLQ_TOKEN.
        timeout: Finite per-RPC response deadline.
        registry_id: Optional expected registry identity.
    """

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        registry: Path | str | None = None,
        token: str | None = None,
        timeout: float = 130,
        registry_id: str | None = None,
    ):
        self._wire = AsyncWire(
            endpoint=endpoint,
            registry=registry,
            token=token,
            timeout=timeout,
            registry_id=registry_id,
        )
        self.clusters = AsyncClusterRegistry(self)

    async def __aenter__(self) -> AsyncMolq:
        try:
            await self._wire.connect()
        except BaseException:
            await self.close()
            raise
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close this client session without cancelling any AsyncJob."""
        await self._wire.close()

    async def rpc(self, method: str, **params: Any) -> Any:
        """Use the same public contract for advanced operations and discovery."""
        return await self._wire.call(
            method, {k: wire_value(v) for k, v in params.items() if v is not None}
        )

    def cluster(self, name: str) -> AsyncCluster:
        """Construct a destination handle; Runtime resolves its registered name."""
        return AsyncCluster(self, name)

    def job(self, ref: dict) -> AsyncJob:
        """Construct a handle to a registry-qualified native allocation."""
        return AsyncJob(self, dict(ref))

    def jobs(self, refs: builtins.list[dict]) -> AsyncJobCollection:
        """Construct one batch observation handle, not one worker per AsyncJob."""
        return AsyncJobCollection(self, list(refs))


class AsyncClusterRegistry:
    """RPC-only access to durable destination definitions."""

    def __init__(self, molq: AsyncMolq):
        self.molq = molq

    async def register(self, **definition: Any) -> AsyncCluster:
        """Register an explicit destination and return its domain handle."""
        result = await self.molq.rpc("clusters.register", **definition)
        return AsyncCluster(self.molq, result["id"])

    async def list(self) -> builtins.list[dict]:
        """List destination definitions without scheduler-state side effects."""
        return await self.molq.rpc("clusters.list")


class AsyncCluster:
    """A destination handle with no Scheduler or SSH implementation."""

    def __init__(self, molq: AsyncMolq, name: str):
        self.molq, self.name = (molq, name)

    async def definition(self) -> dict:
        """Read the Runtime-owned definition and revision."""
        return await self.molq.rpc("clusters.get", cluster=self.name)

    async def update(self, definition: dict, *, expected_revision: int) -> dict:
        """Update destination configuration through a revision-checked RPC."""
        return await self.molq.rpc(
            "clusters.update",
            cluster=self.name,
            definition=definition,
            expected_revision=expected_revision,
        )

    async def remove(self, *, expected_revision: int) -> dict:
        """Remove registry configuration; existing native jobs are not cancelled."""
        return await self.molq.rpc(
            "clusters.remove", cluster=self.name, expected_revision=expected_revision
        )

    async def submit(
        self,
        spec: JobSpec | dict | None = None,
        *,
        argv: builtins.list[str] | None = None,
        request_key: str | None = None,
    ) -> AsyncJob:
        """Submit one allocation; argv is a single-unit convenience constructor."""
        if (spec is None) == (argv is None):
            raise MolqError("INVALID_INPUT", "Provide exactly one of spec or argv")
        if argv is not None:
            spec = JobSpec(Execution((ExecutionUnit.argv("main", argv),)))
        result = await self.molq.rpc(
            "jobs.submit",
            cluster=self.name,
            spec=wire_value(spec),
            request_key=request_key,
        )
        return AsyncJob(self.molq, result["ref"])

    async def validate(self, spec: JobSpec | dict) -> dict:
        """Ask Runtime/Scheduler to validate representation, not resource existence."""
        return await self.molq.rpc(
            "jobs.validate", cluster=self.name, spec=wire_value(spec)
        )

    async def preview(self, spec: JobSpec | dict) -> dict:
        """Use the same Scheduler renderer as submission."""
        return await self.molq.rpc(
            "jobs.preview", cluster=self.name, spec=wire_value(spec)
        )

    async def list(self) -> dict:
        """Query the actual native queue, including jobs submitted outside molq."""
        return await self.molq.rpc("jobs.list", cluster=self.name)

    async def observe(self, *, cursor: str | None = None) -> dict:
        """Request one sample; cadence remains a client choice."""
        return await self.molq.rpc("jobs.observe", cluster=self.name, cursor=cursor)


class AsyncJob:
    """One scheduler allocation; lifecycle interpretation is returned by Runtime."""

    def __init__(self, molq: AsyncMolq, ref: dict):
        self.molq, self.ref = (molq, dict(ref))

    async def status(self, *, consistency: str = "live", max_age: float = 5) -> dict:
        """Return canonical runtime observation with coverage/freshness."""
        return await self.molq.rpc(
            "jobs.get", ref=self.ref, consistency=consistency, max_age=max_age
        )

    async def cancel(self, *, request_key: str | None = None) -> dict:
        """Return cancellation request outcome, never assume terminal state."""
        return await self.molq.rpc("jobs.cancel", ref=self.ref, request_key=request_key)

    async def wait(self, *, timeout: float = 3600, interval: float = 1) -> dict:
        """Delegate shared completion semantics to one batch observation handle."""
        return await self.molq.jobs([self.ref]).wait(timeout=timeout, interval=interval)

    async def logs(
        self, *, stream: str = "stdout", offset: int = 0, limit: int = 262144
    ) -> dict:
        """Read a finite target log chunk through Runtime."""
        return await self.molq.rpc(
            "logs.read", ref=self.ref, stream=stream, offset=offset, limit=limit
        )


class AsyncJobCollection:
    """Batch operations sharing Runtime's collection completion semantics."""

    def __init__(self, molq: AsyncMolq, refs: builtins.list[dict]):
        self.molq, self.refs = (molq, [dict(ref) for ref in refs])

    async def status(self, *, consistency: str = "live", max_age: float = 5) -> dict:
        """Query many refs in AsyncCluster batches."""
        return await self.molq.rpc(
            "jobs.get_many", refs=self.refs, consistency=consistency, max_age=max_age
        )

    async def cancel(self) -> dict:
        """Cancel a batch with explicit per-item outcomes."""
        return await self.molq.rpc("jobs.cancel_many", refs=self.refs)

    async def observe(self, *, cursor: str | None = None) -> dict:
        """Request one runtime-owned diff and completion result."""
        return await self.molq.rpc("jobs.observe", refs=self.refs, cursor=cursor)

    async def wait(self, *, timeout: float = 3600, interval: float = 1) -> dict:
        """Foreground finite sampling; close/deadline never cancels Jobs."""
        if timeout <= 0 or interval <= 0:
            raise MolqError("INVALID_INPUT", "wait timeout/interval must be positive")
        deadline = time.monotonic() + timeout
        cursor = None
        while True:
            result = await self.observe(cursor=cursor)
            cursor = result["cursor"]
            if result["completion"]["all_confirmed_terminal"]:
                return result
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise MolqError("WAIT_TIMEOUT", "Foreground wait deadline reached")
            await asyncio.sleep(min(interval, remaining))
