"""Scheduler contract, normalized truth and finite native operations."""

from __future__ import annotations

import builtins
import posixpath
from dataclasses import dataclass
from typing import Any, Protocol

from molq.errors import MolqError
from molq.transport import Transport

TERMINAL = frozenset({"succeeded", "failed", "cancelled", "timed_out"})


@dataclass(frozen=True)
class NativeJob:
    """Facts read from scheduler/accounting or original Shell receipts."""

    native_id: str
    incarnation: str
    state: str
    source: str
    raw_state: str = ""
    exit_code: int | None = None
    workdir: str | None = None
    name: str | None = None
    stdout_path: str | None = None
    stderr_path: str | None = None


class Scheduler(Protocol):
    """In-process owner of all native scheduler semantics."""

    transport: Transport

    async def submit(self, spec: dict, directory: str) -> NativeJob: ...
    def validate(self, spec: dict) -> None: ...
    def render(self, spec: dict, directory: str) -> str: ...
    async def query_many(self, ids: builtins.list[str]) -> dict[str, NativeJob]: ...
    async def list(self) -> builtins.list[NativeJob]: ...
    async def history(self, ids: builtins.list[str]) -> dict[str, NativeJob]: ...
    async def cancel(self, job: NativeJob) -> dict[str, Any]: ...


class _SchedulerMethods:
    """Shared transport safety and script staging, without a feature inventory."""

    def __init__(self, transport: Transport, cluster: dict):
        self.transport = transport
        self.cluster = cluster

    @staticmethod
    def unsupported(message: str) -> None:
        """Reject inaccurate mappings rather than dropping requested fields."""
        raise MolqError("SCHEDULER_UNSUPPORTED", message)

    async def native(
        self,
        argv: builtins.list[str],
        *,
        mutation: bool = False,
        input: bytes | None = None,
    ) -> str:
        """Execute a native operation; errors never mean absent/terminal."""
        try:
            result = await self.transport.run(argv, timeout=30, input=input)
        except MolqError as exc:
            if mutation and exc.context.get("dispatched") is not False:
                raise MolqError(
                    "OUTCOME_UNKNOWN",
                    "Native mutation outcome is unknown",
                    outcome="unknown",
                    command=argv[0],
                ) from exc
            raise MolqError(
                "SCHEDULER_UNAVAILABLE",
                "Native scheduler operation unavailable",
                command=argv[0],
            ) from exc
        if result.returncode:
            # SSH's 255 means no reliable remote application outcome.
            kind = (
                "OUTCOME_UNKNOWN"
                if mutation and result.returncode == 255
                else ("SUBMISSION_REJECTED" if mutation else "SCHEDULER_UNAVAILABLE")
            )
            raise MolqError(
                kind,
                "Native scheduler command failed",
                outcome="unknown" if kind == "OUTCOME_UNKNOWN" else "not_applied",
                command=argv[0],
                returncode=result.returncode,
                stderr=result.stderr.decode("utf-8", "replace")[:4096],
            )
        return result.text

    def render(self, spec: dict, directory: str) -> str:
        """Implemented by the concrete Scheduler."""
        raise NotImplementedError

    async def query_many(self, ids: builtins.list[str]) -> dict[str, NativeJob]:
        """Implemented by the concrete Scheduler."""
        raise NotImplementedError

    async def accepted_identity(self, identity: str) -> NativeJob:
        """Preserve uncertainty if identity lookup fails after native acceptance."""
        import asyncio

        try:
            for _ in range(4):
                jobs = await self.query_many([identity])
                if identity in jobs and jobs[identity].incarnation:
                    return jobs[identity]
                await asyncio.sleep(0.05)
        except MolqError as exc:
            raise MolqError(
                "OUTCOME_UNKNOWN",
                "Allocation accepted but native identity lookup failed",
                outcome="unknown",
                native_id=identity,
            ) from exc
        raise MolqError(
            "OUTCOME_UNKNOWN",
            "Allocation accepted but native identity evidence unavailable",
            outcome="unknown",
            native_id=identity,
        )

    async def stage(self, spec: dict, directory: str) -> str:
        """Stage only static allocation scripts, never a JobState database."""
        self.validate(spec)
        path = posixpath.join(directory, "job.sh")
        await self.transport.write(path, self.render(spec, directory).encode())
        return path

    def launch(self, unit: dict, payload: str) -> str:
        """Map explicit MPI launcher configuration to native invocation."""
        intent = unit.get("launch", {"kind": "direct"})
        if intent["kind"] == "direct":
            if unit.get("placement"):
                self.unsupported(
                    "Direct unit placement requires native execution-step mapping"
                )
            return payload
        launcher = self.cluster.get("launcher")
        if launcher not in {"mpirun", "mpiexec"}:
            self.unsupported(
                "MPI requires an explicit mpirun/mpiexec binding for this Scheduler"
            )
        flag = "-np" if launcher == "mpirun" else "-n"
        return f"{launcher} {flag} {intent['ranks']} {payload}"

    def validate(self, spec: dict) -> None:
        """Ensure all execution units have accurately representable launch intent."""
        for unit in spec["execution"]["units"]:
            self.launch(unit, "true")
