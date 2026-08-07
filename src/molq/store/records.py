"""Row mapping and dependency-edge evaluation.

Pure functions over SQLite rows — no connection, no I/O — so they can be
tested and reused without a store.
"""

from __future__ import annotations

import json
import sqlite3

from molq.models import JobRecord
from molq.status import JobState


def row_to_record(row: sqlite3.Row) -> JobRecord:
    """Map a ``jobs`` row onto a :class:`~molq.models.JobRecord`.

    An unrecognised state string degrades to ``LOST`` rather than raising: a
    row written by a newer molq should still be listable by an older one.
    """
    try:
        state = JobState(row["state"])
    except ValueError:
        state = JobState.LOST

    return JobRecord(
        job_id=row["job_id"],
        cluster_name=row["cluster_name"],
        scheduler=row["scheduler"],
        state=state,
        scheduler_job_id=row["scheduler_job_id"],
        submitted_at=row["submitted_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        exit_code=row["exit_code"],
        failure_reason=row["failure_reason"],
        cwd=row["cwd"],
        command_type=row["command_type"],
        command_display=row["command_display"],
        metadata=json.loads(row["metadata"] or "{}"),
        root_job_id=row["root_job_id"] or row["job_id"],
        attempt=row["attempt"] or 1,
        previous_attempt_job_id=row["previous_attempt_job_id"],
        retry_group_id=row["retry_group_id"],
        profile_name=row["profile_name"],
        cleaned_at=row["cleaned_at"],
    )


def coerce_job_state(value: str | None) -> JobState:
    try:
        return JobState(value) if value is not None else JobState.LOST
    except ValueError:
        return JobState.LOST


def dependency_relation_state(
    dependency_type: str,
    related_state: JobState,
    related_started_at: float | None,
) -> str:
    """Evaluate whether a single dependency edge is satisfied, pending, or impossible.

    Args:
        dependency_type: One of the canonical ``DependencyCondition`` values
            (``"after_success"``, ``"after_failure"``, ``"after_started"``,
            ``"after"``).
        related_state: Current ``JobState`` of the upstream job.
        related_started_at: Unix timestamp of when the upstream job started
            executing, or ``None`` if it has not started yet.

    Returns:
        ``"satisfied"`` — the condition is already met.
        ``"pending"``   — the upstream job has not reached the required state.
        ``"impossible"`` — the upstream job reached a terminal state that can
            never satisfy the condition (e.g. ``after_success`` on a failed job).

    Raises:
        ValueError: If *dependency_type* is not a recognised condition name.
    """
    if dependency_type == "after_success":
        if related_state == JobState.SUCCEEDED:
            return "satisfied"
        if related_state.is_terminal:
            return "impossible"
        return "pending"

    if dependency_type == "after_failure":
        if related_state in {
            JobState.FAILED,
            JobState.CANCELLED,
            JobState.TIMED_OUT,
            JobState.LOST,
        }:
            return "satisfied"
        if related_state == JobState.SUCCEEDED:
            return "impossible"
        return "pending"

    if dependency_type == "after_started":
        if related_started_at is not None or related_state in {
            JobState.RUNNING,
            JobState.SUCCEEDED,
            JobState.FAILED,
            JobState.CANCELLED,
            JobState.TIMED_OUT,
            JobState.LOST,
        }:
            return "satisfied"
        return "pending"

    if dependency_type == "after":
        return "satisfied" if related_state.is_terminal else "pending"

    raise ValueError(
        f"Unknown dependency condition {dependency_type!r}. "
        "Valid values: 'after_success', 'after_failure', 'after_started', 'after'."
    )
