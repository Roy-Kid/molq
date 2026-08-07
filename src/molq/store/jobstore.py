"""Job persistence for molq.

SQLite with WAL mode, UUID job identity, and schema versioning.  DDL and
migrations live in :mod:`molq.store.schema`; row mapping and dependency
evaluation in :mod:`molq.store.records`.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Sequence
from pathlib import Path

from molcfg.paths import project_config_dir

from molq.models import (
    DependencyPreview,
    DependencyPreviewItem,
    JobDependency,
    JobRecord,
    JobSpec,
    RememberedAllocation,
    StatusTransition,
)
from molq.status import JobState
from molq.store.records import (
    coerce_job_state,
    dependency_relation_state,
    row_to_record,
)
from molq.store.schema import _ALLOC_KEY_SEP, SchemaMixin
from molq.types import JobScheduling


def default_jobs_db_path() -> Path:
    """Return the canonical molq jobs.db path, bootstrapping the dir.

    Delegates to :func:`molcfg.paths.project_config_dir`, which
    resolves ``~/.molcrafts/molq/config/`` (honouring the
    ``MOLCRAFTS_HOME`` env var) and creates it idempotently on first
    call. The returned path always points at
    ``<that dir>/jobs.db`` — the file itself is created by SQLite when
    :class:`JobStore` opens its connection.

    This is the only sanctioned source of a default DB location.
    :class:`JobStore` no longer silently falls back to a built-in
    path; callers that want the standard location must pass
    ``JobStore(default_jobs_db_path())`` explicitly.
    """
    return project_config_dir("molq") / "jobs.db"


def _alloc_key(scheduling: JobScheduling) -> str:
    """Normalized identity for an allocation: partition/account/qos/reservation.

    ``None`` is encoded as an empty segment so a missing field and an empty
    string collapse to the same key, and so SQLite's "every NULL is distinct"
    rule cannot create duplicate rows for the same logical config.
    """
    return _ALLOC_KEY_SEP.join(
        value or ""
        for value in (
            scheduling.partition,
            scheduling.account,
            scheduling.qos,
            scheduling.reservation,
        )
    )


class JobStore(SchemaMixin):
    """SQLite-backed job persistence with WAL mode.

    Args:
        db_path: Path to database file. Use ``':memory:'`` for testing.
            Required — no silent fallback. For the canonical
            molcrafts location, pass
            ``default_jobs_db_path()``.
    """

    # Always set after __init__; close() flips it to None as an escape hatch
    # so __del__ can be idempotent.  The type annotation captures the
    # normal-operation invariant — calls after close() raise via SQLite's
    # own "Cannot operate on a closed database" error.
    _conn: sqlite3.Connection

    def __init__(self, db_path: Path | str) -> None:
        if db_path is None:
            raise TypeError(
                "JobStore(db_path) requires an explicit path. "
                "For the canonical molcrafts location, pass "
                "`default_jobs_db_path()` from molq.store."
            )

        self.db_path = Path(db_path) if db_path != ":memory:" else db_path
        self._write_lock = threading.RLock()
        self._conn = self._open_connection()
        with self._write_lock:
            self._ensure_schema()

    def _open_connection(self) -> sqlite3.Connection:
        path = str(self.db_path)
        conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def compare_and_update_state(
        self,
        job_id: str,
        expected_state: JobState,
        new_state: JobState,
        *,
        started_at: float | None = None,
        finished_at: float | None = None,
        last_polled: float | None = None,
        exit_code: int | None = None,
        failure_reason: str | None = None,
        cleaned_at: float | None = None,
    ) -> bool:
        """Atomically update state iff current state matches ``expected_state``.

        Returns True if the row was updated, False if the precondition failed.
        """
        fields: list[str] = ["state = ?"]
        values: list[object] = [new_state.value]

        extras = {
            "started_at": started_at,
            "finished_at": finished_at,
            "last_polled": last_polled,
            "exit_code": exit_code,
            "failure_reason": failure_reason,
            "cleaned_at": cleaned_at,
        }
        for col, val in extras.items():
            if val is not None:
                fields.append(f"{col} = ?")
                values.append(val)

        values.extend([job_id, expected_state.value])
        sql = f"UPDATE jobs SET {', '.join(fields)} WHERE job_id = ? AND state = ?"

        with self._write_lock:
            cur = self._conn.execute(sql, tuple(values))
            self._conn.commit()
            return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def insert_job(self, spec: JobSpec) -> None:
        """Insert a new job record from a JobSpec."""
        now = time.time()
        with self._write_lock:
            self._conn.execute(
                """INSERT INTO jobs
                (job_id, cluster_name, scheduler, root_job_id, attempt,
                 previous_attempt_job_id, retry_group_id, state,
                 command_type, command_display, cwd,
                 submitted_at, metadata, request_json, profile_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    spec.job_id,
                    spec.cluster_name,
                    spec.scheduler,
                    spec.root_job_id or spec.job_id,
                    spec.attempt,
                    spec.previous_attempt_job_id,
                    spec.retry_group_id or spec.root_job_id or spec.job_id,
                    JobState.CREATED.value,
                    spec.command.command_type,
                    spec.command.display,
                    spec.cwd,
                    now,
                    json.dumps(spec.metadata),
                    spec.request_json,
                    spec.profile_name,
                ),
            )
            self._conn.execute(
                """INSERT INTO status_transitions
                (job_id, old_state, new_state, timestamp, reason)
                VALUES (?, ?, ?, ?, ?)""",
                (spec.job_id, None, JobState.CREATED.value, now, "job created"),
            )
            self._conn.commit()

    def update_job(
        self,
        job_id: str,
        *,
        state: JobState | None = None,
        scheduler_job_id: str | None = None,
        submitted_at: float | None = None,
        started_at: float | None = None,
        finished_at: float | None = None,
        last_polled: float | None = None,
        exit_code: int | None = None,
        failure_reason: str | None = None,
        cleaned_at: float | None = None,
    ) -> None:
        """Partial update of a job record."""
        fields: list[str] = []
        values: list[object] = []

        updates = {
            "state": state.value if state else None,
            "scheduler_job_id": scheduler_job_id,
            "submitted_at": submitted_at,
            "started_at": started_at,
            "finished_at": finished_at,
            "last_polled": last_polled,
            "exit_code": exit_code,
            "failure_reason": failure_reason,
            "cleaned_at": cleaned_at,
        }

        for col, val in updates.items():
            if val is not None:
                fields.append(f"{col} = ?")
                values.append(val)

        if not fields:
            return

        values.append(job_id)
        sql = f"UPDATE jobs SET {', '.join(fields)} WHERE job_id = ?"

        with self._write_lock:
            self._conn.execute(sql, tuple(values))
            self._conn.commit()

    def mark_polled(self, job_ids: Sequence[str], timestamp: float) -> None:
        """Stamp ``last_polled`` on many jobs in one transaction.

        The reconciler touches every active job on each cycle.  Doing that
        one :meth:`update_job` at a time costs a commit (and an fsync) per
        job per cycle; batching keeps a poll cycle at a single write
        regardless of how many jobs are in flight.
        """
        if not job_ids:
            return
        unique = tuple(dict.fromkeys(job_ids))
        placeholders = ",".join("?" for _ in unique)
        with self._write_lock:
            self._conn.execute(
                f"UPDATE jobs SET last_polled = ? WHERE job_id IN ({placeholders})",
                (timestamp, *unique),
            )
            self._conn.commit()

    def record_allocation(
        self,
        cluster_name: str,
        scheduling: JobScheduling,
        *,
        now: float | None = None,
    ) -> None:
        """Remember a scheduling config used to submit to *cluster_name*.

        Upserts on the normalized (partition, account, qos, reservation)
        identity: a first use inserts with ``use_count=1``; a repeat bumps
        ``use_count`` and refreshes ``last_used``.  Configs with none of the
        four identity fields set are ignored (nothing worth remembering).
        This memory is independent of the ``jobs`` table, so retention cleanup
        of old jobs never erases it.
        """
        if not any(
            (
                scheduling.partition,
                scheduling.account,
                scheduling.qos,
                scheduling.reservation,
            )
        ):
            return
        ts = time.time() if now is None else now
        with self._write_lock:
            self._conn.execute(
                """INSERT INTO allocations
                (cluster_name, alloc_key, partition, account, qos, reservation,
                 label, first_used, last_used, use_count)
                VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, 1)
                ON CONFLICT(cluster_name, alloc_key) DO UPDATE SET
                    last_used = excluded.last_used,
                    use_count = use_count + 1""",
                (
                    cluster_name,
                    _alloc_key(scheduling),
                    scheduling.partition,
                    scheduling.account,
                    scheduling.qos,
                    scheduling.reservation,
                    ts,
                    ts,
                ),
            )
            self._conn.commit()

    def list_allocations(
        self,
        cluster_name: str,
        *,
        limit: int | None = None,
    ) -> list[RememberedAllocation]:
        """Return remembered allocations for *cluster_name*, most-recent first."""
        sql = (
            "SELECT partition, account, qos, reservation, label, "
            "last_used, use_count FROM allocations "
            "WHERE cluster_name = ? ORDER BY last_used DESC"
        )
        params: list[object] = [cluster_name]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        rows = self._conn.execute(sql, tuple(params)).fetchall()
        return [
            RememberedAllocation(
                partition=row["partition"],
                account=row["account"],
                qos=row["qos"],
                reservation=row["reservation"],
                label=row["label"],
                last_used=row["last_used"],
                use_count=row["use_count"],
            )
            for row in rows
        ]

    def add_dependencies(
        self,
        job_id: str,
        dependencies: list[JobDependency],
    ) -> None:
        if not dependencies:
            return
        with self._write_lock:
            self._conn.executemany(
                """INSERT INTO job_dependencies
                (job_id, dependency_job_id, dependency_type, scheduler_dependency)
                VALUES (?, ?, ?, ?)""",
                [
                    (
                        dep.job_id,
                        dep.dependency_job_id,
                        dep.dependency_type,
                        dep.scheduler_dependency,
                    )
                    for dep in dependencies
                ],
            )
            self._conn.commit()

    def record_transition(
        self,
        job_id: str,
        old_state: JobState | None,
        new_state: JobState,
        timestamp: float,
        reason: str | None = None,
    ) -> None:
        """Record a status transition."""
        with self._write_lock:
            self._conn.execute(
                """INSERT INTO status_transitions
                (job_id, old_state, new_state, timestamp, reason)
                VALUES (?, ?, ?, ?, ?)""",
                (
                    job_id,
                    old_state.value if old_state else None,
                    new_state.value,
                    timestamp,
                    reason,
                ),
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_record(self, job_id: str) -> JobRecord | None:
        """Get a single job record by ID."""
        row = self._conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        if row is None:
            return None
        return row_to_record(row)

    def list_records(
        self,
        cluster_name: str,
        include_terminal: bool = False,
        limit: int | None = None,
    ) -> list[JobRecord]:
        """List job records for a cluster, newest first.

        Args:
            cluster_name: Scope records to this cluster.
            include_terminal: Include finished jobs.  With ``True`` this spans
                the cluster's whole history, so pass *limit* for interactive
                callers.
            limit: Cap the result set.  ``None`` returns every matching row.
        """
        params: list[object] = [cluster_name]
        if include_terminal:
            sql = "SELECT * FROM jobs WHERE cluster_name = ?"
        else:
            terminal = tuple(s.value for s in JobState if s.is_terminal)
            placeholders = ",".join("?" for _ in terminal)
            sql = (
                f"SELECT * FROM jobs WHERE cluster_name = ? "
                f"AND state NOT IN ({placeholders})"
            )
            params.extend(terminal)
        sql += " ORDER BY submitted_at DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))

        rows = self._conn.execute(sql, tuple(params)).fetchall()
        return [row_to_record(row) for row in rows]

    def get_active_records(self, cluster_name: str) -> list[JobRecord]:
        """Get all non-terminal job records for a cluster."""
        return self.list_records(cluster_name, include_terminal=False)

    def list_all_records(
        self,
        include_terminal: bool = False,
        limit: int | None = None,
    ) -> list[JobRecord]:
        """List job records across **all** clusters, ordered by submission time.

        Args:
            include_terminal: When ``False`` (default), terminal states
                (succeeded, failed, cancelled, timed_out, lost) are excluded.
            limit: Cap the result set.  ``None`` returns all matching rows.

        Returns:
            List of :class:`JobRecord`, newest first.
        """
        if include_terminal:
            sql = "SELECT * FROM jobs ORDER BY submitted_at DESC"
            params: tuple = ()
        else:
            terminal = tuple(s.value for s in JobState if s.is_terminal)
            placeholders = ",".join("?" for _ in terminal)
            sql = (
                f"SELECT * FROM jobs WHERE state NOT IN ({placeholders}) "
                f"ORDER BY submitted_at DESC"
            )
            params = terminal

        if limit is not None:
            sql += f" LIMIT {int(limit)}"

        rows = self._conn.execute(sql, params).fetchall()
        return [row_to_record(row) for row in rows]

    def get_transitions(self, job_id: str) -> list[StatusTransition]:
        """Return the persisted transition timeline for a job."""
        rows = self._conn.execute(
            "SELECT job_id, old_state, new_state, timestamp, reason "
            "FROM status_transitions WHERE job_id = ? "
            "ORDER BY timestamp ASC, id ASC",
            (job_id,),
        ).fetchall()
        return [
            StatusTransition(
                job_id=row["job_id"],
                old_state=JobState(row["old_state"]) if row["old_state"] else None,
                new_state=JobState(row["new_state"]),
                timestamp=row["timestamp"],
                reason=row["reason"],
            )
            for row in rows
        ]

    def get_dependencies(self, job_id: str) -> list[JobDependency]:
        rows = self._conn.execute(
            "SELECT job_id, dependency_job_id, dependency_type, scheduler_dependency "
            "FROM job_dependencies WHERE job_id = ? ORDER BY id ASC",
            (job_id,),
        ).fetchall()
        return [
            JobDependency(
                job_id=row["job_id"],
                dependency_job_id=row["dependency_job_id"],
                dependency_type=row["dependency_type"],
                scheduler_dependency=row["scheduler_dependency"],
            )
            for row in rows
        ]

    def get_dependents(self, job_id: str) -> list[JobDependency]:
        rows = self._conn.execute(
            "SELECT job_id, dependency_job_id, dependency_type, scheduler_dependency "
            "FROM job_dependencies WHERE dependency_job_id = ? ORDER BY id ASC",
            (job_id,),
        ).fetchall()
        return [
            JobDependency(
                job_id=row["job_id"],
                dependency_job_id=row["dependency_job_id"],
                dependency_type=row["dependency_type"],
                scheduler_dependency=row["scheduler_dependency"],
            )
            for row in rows
        ]

    def get_dependency_previews(
        self,
        job_ids: Sequence[str],
        *,
        max_items: int = 8,
    ) -> dict[str, DependencyPreview]:
        unique_job_ids = tuple(dict.fromkeys(job_ids))
        if not unique_job_ids:
            return {}

        placeholders = ",".join("?" for _ in unique_job_ids)
        owner_rows = self._conn.execute(
            f"SELECT job_id, state, started_at FROM jobs WHERE job_id IN ({placeholders})",
            unique_job_ids,
        ).fetchall()
        owner_state_map = {
            row["job_id"]: (
                coerce_job_state(row["state"]),
                row["started_at"],
            )
            for row in owner_rows
        }

        upstream_total = {job_id: 0 for job_id in unique_job_ids}
        upstream_satisfied = {job_id: 0 for job_id in unique_job_ids}
        upstream_items = {job_id: [] for job_id in unique_job_ids}
        downstream_total = {job_id: 0 for job_id in unique_job_ids}
        downstream_items = {job_id: [] for job_id in unique_job_ids}

        upstream_rows = self._conn.execute(
            "SELECT d.job_id, d.dependency_job_id, d.dependency_type, d.scheduler_dependency, "
            "u.state AS related_state, u.started_at AS related_started_at, "
            "u.command_display AS related_command_display "
            f"FROM job_dependencies d JOIN jobs u ON u.job_id = d.dependency_job_id "
            f"WHERE d.job_id IN ({placeholders}) ORDER BY d.id ASC",
            unique_job_ids,
        ).fetchall()

        for row in upstream_rows:
            owner_job_id = row["job_id"]
            related_state = coerce_job_state(row["related_state"])
            relation_state = dependency_relation_state(
                row["dependency_type"],
                related_state,
                row["related_started_at"],
            )
            upstream_total[owner_job_id] += 1
            if relation_state == "satisfied":
                upstream_satisfied[owner_job_id] += 1
            if len(upstream_items[owner_job_id]) < max_items:
                upstream_items[owner_job_id].append(
                    DependencyPreviewItem(
                        job_id=row["dependency_job_id"],
                        dependency_type=row["dependency_type"],
                        relation_state=relation_state,
                        job_state=related_state,
                        command_display=row["related_command_display"] or "",
                        scheduler_dependency=row["scheduler_dependency"],
                    )
                )

        downstream_rows = self._conn.execute(
            "SELECT d.dependency_job_id, d.job_id AS dependent_job_id, "
            "d.dependency_type, d.scheduler_dependency, "
            "j.state AS related_state, j.command_display AS related_command_display "
            f"FROM job_dependencies d JOIN jobs j ON j.job_id = d.job_id "
            f"WHERE d.dependency_job_id IN ({placeholders}) ORDER BY d.id ASC",
            unique_job_ids,
        ).fetchall()

        for row in downstream_rows:
            owner_job_id = row["dependency_job_id"]
            owner_state, owner_started_at = owner_state_map.get(
                owner_job_id, (JobState.LOST, None)
            )
            relation_state = dependency_relation_state(
                row["dependency_type"],
                owner_state,
                owner_started_at,
            )
            downstream_total[owner_job_id] += 1
            if len(downstream_items[owner_job_id]) < max_items:
                downstream_items[owner_job_id].append(
                    DependencyPreviewItem(
                        job_id=row["dependent_job_id"],
                        dependency_type=row["dependency_type"],
                        relation_state=relation_state,
                        job_state=coerce_job_state(row["related_state"]),
                        command_display=row["related_command_display"] or "",
                        scheduler_dependency=row["scheduler_dependency"],
                    )
                )

        return {
            job_id: DependencyPreview(
                job_id=job_id,
                upstream_total=upstream_total[job_id],
                upstream_satisfied=upstream_satisfied[job_id],
                upstream=tuple(upstream_items[job_id]),
                downstream_total=downstream_total[job_id],
                downstream=tuple(downstream_items[job_id]),
            )
            for job_id in unique_job_ids
        }

    def get_retry_family(self, job_id: str) -> list[JobRecord]:
        record = self.get_record(job_id)
        if record is None:
            return []
        rows = self._conn.execute(
            "SELECT * FROM jobs WHERE root_job_id = ? ORDER BY attempt ASC, submitted_at ASC",
            (record.root_job_id or record.job_id,),
        ).fetchall()
        return [row_to_record(row) for row in rows]

    def get_latest_attempt_record(self, job_id: str) -> JobRecord | None:
        """Return the newest attempt in *job_id*'s retry family.

        Resolves the family root in a subquery rather than a separate
        round trip — the monitor calls this on every poll.
        """
        row = self._conn.execute(
            "SELECT * FROM jobs WHERE root_job_id = ("
            "  SELECT COALESCE(NULLIF(root_job_id, ''), job_id)"
            "  FROM jobs WHERE job_id = ?"
            ") ORDER BY attempt DESC, submitted_at DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        return row_to_record(row)

    def get_request_json(self, job_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT request_json FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        return row["request_json"]

    def list_cleanup_candidates(
        self,
        cluster_name: str,
        *,
        job_dir_cutoff: float,
        record_cutoff: float,
        include_failed_job_dirs: bool,
    ) -> tuple[list[JobRecord], list[JobRecord]]:
        # Both cutoffs are expressed in SQL: loading every terminal record for
        # the cluster just to filter it in Python made cleanup cost scale with
        # total history rather than with the number of expiring rows.
        terminal = tuple(s.value for s in JobState if s.is_terminal)
        placeholders = ",".join("?" for _ in terminal)
        base = (
            f"SELECT * FROM jobs WHERE cluster_name = ? "
            f"AND state IN ({placeholders}) "
            f"AND finished_at IS NOT NULL AND finished_at > 0"
        )

        artifact_sql = f"{base} AND cleaned_at IS NULL AND finished_at <= ?"
        artifact_params: list[object] = [cluster_name, *terminal, job_dir_cutoff]
        if not include_failed_job_dirs:
            keep = (
                JobState.FAILED.value,
                JobState.TIMED_OUT.value,
                JobState.LOST.value,
            )
            keep_placeholders = ",".join("?" for _ in keep)
            artifact_sql += f" AND state NOT IN ({keep_placeholders})"
            artifact_params.extend(keep)
        artifact_sql += " ORDER BY finished_at ASC"

        artifact_rows = self._conn.execute(
            artifact_sql, tuple(artifact_params)
        ).fetchall()
        record_rows = self._conn.execute(
            f"{base} AND finished_at <= ? ORDER BY finished_at ASC",
            (cluster_name, *terminal, record_cutoff),
        ).fetchall()

        return (
            [row_to_record(row) for row in artifact_rows],
            [row_to_record(row) for row in record_rows],
        )

    def delete_terminal_records(self, job_ids: list[str]) -> None:
        if not job_ids:
            return
        placeholders = ",".join("?" for _ in job_ids)
        with self._write_lock:
            self._conn.execute(
                f"DELETE FROM job_dependencies WHERE job_id IN ({placeholders}) "
                f"OR dependency_job_id IN ({placeholders})",
                tuple(job_ids) + tuple(job_ids),
            )
            self._conn.execute(
                f"DELETE FROM status_transitions WHERE job_id IN ({placeholders})",
                tuple(job_ids),
            )
            self._conn.execute(
                f"DELETE FROM jobs WHERE job_id IN ({placeholders})",
                tuple(job_ids),
            )
            self._conn.commit()

    def close(self) -> None:
        """Close the database connection.  Idempotent."""
        conn = getattr(self, "_conn", None)
        if conn is None:
            return
        try:
            conn.close()
        finally:
            self._conn = None  # ty: ignore[invalid-assignment]

    def __del__(self) -> None:
        # Finalizer guard: if the user forgot to call close(), at least
        # silence the sqlite3 ResourceWarning instead of leaking the FD.
        # Module-level state may already be torn down at interpreter
        # shutdown, so swallow everything.
        try:
            self.close()
        except Exception:
            pass
