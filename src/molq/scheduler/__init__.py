"""Scheduler backends for molq.

Internal package — users interact through
:class:`~molq.submitor.Submitor`, not with a Scheduler directly.

Every backend implements the :class:`~molq.scheduler.base.Scheduler` protocol
and routes each shell call through an injected
:class:`~molq.transport.Transport`, so any Scheduler x Transport pairing works.
Adding a backend means adding a module here — nothing outside this package
encodes per-scheduler syntax.

The public names are re-exported so ``from molq.scheduler import
SlurmScheduler`` keeps working.
"""

from __future__ import annotations

from molq.options import (
    LocalSchedulerOptions,
    LSFSchedulerOptions,
    PBSSchedulerOptions,
    SchedulerOptions,
    SlurmSchedulerOptions,
)
from molq.scheduler.base import (
    DependencyEdge,
    QueueEntry,
    Scheduler,
    SchedulerCapabilities,
    TerminalStatus,
)
from molq.scheduler.lsf import LSFScheduler
from molq.scheduler.pbs import PBSScheduler
from molq.scheduler.shell import ShellScheduler
from molq.scheduler.slurm import SlurmScheduler
from molq.transport import Transport

# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_scheduler(
    scheduler_name: str,
    options: SchedulerOptions | None = None,
    *,
    transport: Transport | None = None,
) -> ShellScheduler | SlurmScheduler | PBSScheduler | LSFScheduler:
    """Create a Scheduler implementation by name.

    Pipelines are built by composing a :class:`Scheduler` with a
    :class:`~molq.transport.Transport`.  ``"local"`` is the no-batch-system
    backend (:class:`ShellScheduler`); the transport decides whether commands
    run on this host (:class:`~molq.transport.LocalTransport`) or on a remote
    workstation (:class:`~molq.transport.SshTransport`).  ``"slurm"``,
    ``"pbs"`` and ``"lsf"`` route batch commands through the same transport.
    """
    if scheduler_name == "local":
        return ShellScheduler(
            options if isinstance(options, LocalSchedulerOptions) else None,
            transport=transport,
        )
    if scheduler_name == "slurm":
        return SlurmScheduler(
            options if isinstance(options, SlurmSchedulerOptions) else None,
            transport=transport,
        )
    if scheduler_name == "pbs":
        return PBSScheduler(
            options if isinstance(options, PBSSchedulerOptions) else None,
            transport=transport,
        )
    if scheduler_name == "lsf":
        return LSFScheduler(
            options if isinstance(options, LSFSchedulerOptions) else None,
            transport=transport,
        )
    raise ValueError(f"Unknown scheduler: {scheduler_name!r}")


__all__ = [
    "DependencyEdge",
    "LSFScheduler",
    "PBSScheduler",
    "QueueEntry",
    "Scheduler",
    "SchedulerCapabilities",
    "ShellScheduler",
    "SlurmScheduler",
    "TerminalStatus",
    "create_scheduler",
]
