"""molq 0.9: peer RPC clients with an immutable OOP Python façade."""

from __future__ import annotations

from molq.domain import (
    Accelerator,
    Execution,
    ExecutionUnit,
    JobSpec,
    Launch,
    Parallel,
    Resources,
    Scheduling,
    Sequence,
    UnitRef,
)
from molq.errors import MolqError

__version__ = "0.9.0"
__all__ = [
    "Molq",
    "AsyncMolq",
    "Cluster",
    "Job",
    "JobCollection",
    "MolqError",
    "Accelerator",
    "Resources",
    "Scheduling",
    "Launch",
    "Execution",
    "ExecutionUnit",
    "UnitRef",
    "Sequence",
    "Parallel",
    "JobSpec",
]


def __getattr__(name: str):
    """Load client façades without importing Runtime or its dependencies."""
    if name in {"Molq", "Cluster", "Job", "JobCollection"}:
        from molq.client import objects

        return getattr(objects, name)
    if name == "AsyncMolq":
        from molq.client.async_objects import AsyncMolq

        return AsyncMolq
    raise AttributeError(name)
