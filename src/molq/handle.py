"""JobHandle — the per-job view returned by :meth:`Submitor.submit_job`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from molq.models import JobRecord
from molq.status import JobState

if TYPE_CHECKING:
    from molq.submitor import Submitor


@dataclass
class JobHandle:
    """Lightweight handle for a submitted job.

    Returned by Submitor.submit(). Provides single-job operations.
    """

    job_id: str
    cluster_name: str
    scheduler: str
    scheduler_job_id: str | None
    _state: JobState
    _submitor: Submitor

    def status(self) -> JobState:
        """Return cached job state (no I/O)."""
        return self._state

    def refresh(self) -> JobHandle:
        """Reconcile with scheduler and return updated handle."""
        latest = self._submitor._store.get_latest_attempt_record(self.job_id)
        watched_job_id = latest.job_id if latest is not None else self.job_id
        new_state = self._submitor._reconciler.reconcile_one(watched_job_id)
        latest = self._submitor._store.get_latest_attempt_record(self.job_id)
        if new_state is not None:
            self._state = new_state
        if latest is not None:
            self.scheduler_job_id = latest.scheduler_job_id
        return self

    def wait(self, timeout: float | None = None) -> JobRecord:
        """Block until this job reaches a terminal state."""
        return self._submitor._monitor_instance.wait_one(
            self.job_id,
            timeout=timeout,
        )

    def cancel(self) -> None:
        """Cancel this job."""
        self._submitor.cancel_job(self.job_id)
        self._state = JobState.CANCELLED
