"""Explicit Scheduler assembly; no business logic branches above this layer."""

from __future__ import annotations

from molq.scheduler.base import NativeJob, Scheduler
from molq.scheduler.lsf import LSFScheduler
from molq.scheduler.pbs import PBSScheduler
from molq.scheduler.shell import ShellScheduler
from molq.scheduler.slurm import SlurmScheduler
from molq.transport import Transport


def create_scheduler(cluster: dict, transport: Transport) -> Scheduler:
    """Select an explicitly registered in-process implementation."""
    return {
        "shell": ShellScheduler,
        "slurm": SlurmScheduler,
        "pbs": PBSScheduler,
        "lsf": LSFScheduler,
    }[cluster["scheduler"]](transport, cluster)


__all__ = [
    "Scheduler",
    "SlurmScheduler",
    "PBSScheduler",
    "LSFScheduler",
    "ShellScheduler",
    "NativeJob",
    "create_scheduler",
]
