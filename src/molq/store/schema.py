"""Database schema: version, DDL, and migrations.

The DDL constants and the migration ladder change on a different cadence from
the query surface, so they live apart from :class:`~molq.store.JobStore`.
:class:`SchemaMixin` carries the migration routines; ``JobStore`` mixes it in
so the call sites stay unchanged.
"""

from __future__ import annotations

import sqlite3
import sys
import threading
from pathlib import Path

from molq.errors import StoreError

_SCHEMA_VERSION = "8"

# Separator for the normalized allocation identity key.  Using the ASCII unit
# separator (never present in partition/account names) lets NULL-vs-empty be
# encoded unambiguously, sidestepping SQLite's "NULLs are distinct" behaviour
# in unique constraints.
_ALLOC_KEY_SEP = "\x1f"

_CREATE_META = """
CREATE TABLE IF NOT EXISTS molq_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""

# v3: dropped UNIQUE(cluster_name, scheduler_job_id).  job_id (UUID) already
# guarantees row identity, and OS-level PID reuse used to make the constraint
# fire spuriously when the local scheduler reused a freed PID.
_CREATE_JOBS = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    cluster_name TEXT NOT NULL,
    scheduler TEXT NOT NULL,
    root_job_id TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 1,
    previous_attempt_job_id TEXT,
    retry_group_id TEXT,
    scheduler_job_id TEXT,
    state TEXT NOT NULL DEFAULT 'created',
    command_type TEXT NOT NULL,
    command_display TEXT NOT NULL,
    cwd TEXT NOT NULL,
    submitted_at REAL,
    started_at REAL,
    finished_at REAL,
    last_polled REAL,
    exit_code INTEGER,
    failure_reason TEXT,
    metadata TEXT DEFAULT '{}',
    request_json TEXT DEFAULT '{}',
    profile_name TEXT,
    cleaned_at REAL
)
"""

_CREATE_TRANSITIONS = """
CREATE TABLE IF NOT EXISTS status_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES jobs(job_id),
    old_state TEXT,
    new_state TEXT NOT NULL,
    timestamp REAL NOT NULL,
    reason TEXT
)
"""

_CREATE_IDX_CLUSTER_STATE = """
CREATE INDEX IF NOT EXISTS idx_jobs_cluster_state
ON jobs(cluster_name, state)
"""

_CREATE_IDX_ROOT_ATTEMPT = """
CREATE INDEX IF NOT EXISTS idx_jobs_root_attempt
ON jobs(root_job_id, attempt)
"""

_CREATE_IDX_RETRY_GROUP = """
CREATE INDEX IF NOT EXISTS idx_jobs_retry_group
ON jobs(retry_group_id)
"""

_CREATE_IDX_TRANSITIONS = """
CREATE INDEX IF NOT EXISTS idx_transitions_job
ON status_transitions(job_id)
"""

_CREATE_DEPENDENCIES = """
CREATE TABLE IF NOT EXISTS job_dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES jobs(job_id),
    dependency_job_id TEXT NOT NULL REFERENCES jobs(job_id),
    dependency_type TEXT NOT NULL,
    scheduler_dependency TEXT NOT NULL
)
"""

_CREATE_IDX_DEPENDENCIES = """
CREATE INDEX IF NOT EXISTS idx_job_dependencies_job
ON job_dependencies(job_id)
"""

_CREATE_ALLOCATIONS = """
CREATE TABLE IF NOT EXISTS allocations (
    cluster_name TEXT NOT NULL,
    alloc_key    TEXT NOT NULL,
    partition    TEXT,
    account      TEXT,
    qos          TEXT,
    reservation  TEXT,
    label        TEXT,
    first_used   REAL NOT NULL,
    last_used    REAL NOT NULL,
    use_count    INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (cluster_name, alloc_key)
)
"""

_CREATE_IDX_ALLOCATIONS = """
CREATE INDEX IF NOT EXISTS idx_allocations_cluster_recency
ON allocations(cluster_name, last_used DESC)
"""


class SchemaMixin:
    """Schema creation and migration for :class:`~molq.store.JobStore`.

    The attribute and method declarations below are the contract the mixin
    expects from its host class; ``JobStore`` provides all of them.
    """

    _conn: sqlite3.Connection
    _write_lock: threading.RLock
    db_path: Path | str

    def _open_connection(self) -> sqlite3.Connection:  # pragma: no cover - host
        raise NotImplementedError

    def _ensure_schema(self) -> None:
        """Check schema version and create/migrate as needed."""
        try:
            row = self._conn.execute(
                "SELECT value FROM molq_meta WHERE key = 'schema_version'"
            ).fetchone()
            if row:
                version = row["value"]
                if version == _SCHEMA_VERSION:
                    return
                # Compare numerically: as strings "10" sorts *before* "8",
                # so a future schema would be misreported as unknown rather
                # than as "upgrade molq".
                try:
                    version_num = int(version)
                except (TypeError, ValueError):
                    raise StoreError(
                        f"Unknown schema version {version!r}; cannot migrate."
                    ) from None
                if version_num > int(_SCHEMA_VERSION):
                    raise StoreError(
                        f"Database schema version {version} is newer than "
                        f"supported version {_SCHEMA_VERSION}. "
                        f"Please upgrade molq."
                    )
                if 2 <= version_num < int(_SCHEMA_VERSION):
                    self._migrate_from_known_version(version)
                    return
                raise StoreError(f"Unknown schema version {version!r}; cannot migrate.")
        except sqlite3.OperationalError:
            # molq_meta table does not exist
            if self._has_old_schema():
                self._migrate_from_v1()
                return

        # Fresh database or needs schema creation
        self._create_schema()

    def _has_old_schema(self) -> bool:
        """Check if this is a v1 database (has 'jobs' table but no 'molq_meta')."""
        try:
            row = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"
            ).fetchone()
            return row is not None
        except sqlite3.OperationalError:
            return False

    def _migrate_from_v1(self) -> None:
        """Back up v1 database and create fresh v3 schema."""
        self._conn.close()

        if isinstance(self.db_path, Path):
            backup_path = self.db_path.with_suffix(".db.v1.bak")
            self.db_path.rename(backup_path)
            print(
                f"molq: migrated database to v{_SCHEMA_VERSION}, "
                f"old data backed up to {backup_path}",
                file=sys.stderr,
            )

        self._conn = self._open_connection()
        self._create_schema()

    def _migrate_from_known_version(self, version: str) -> None:
        if version == "2":
            self._migrate_v2_to_current()
            return
        if 3 <= int(version) < int(_SCHEMA_VERSION):
            self._migrate_v3plus_to_current()
            return
        raise StoreError(f"Unknown schema version {version!r}; cannot migrate.")

    def _migrate_v2_to_current(self) -> None:
        """Migrate the v2 jobs table directly to the current schema.

        SQLite cannot drop table constraints in place, so we recreate the
        ``jobs`` table without the constraint and copy rows over.  The whole
        operation runs inside a single transaction so concurrent readers
        always observe a consistent snapshot.
        """
        with self._write_lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute("ALTER TABLE jobs RENAME TO _jobs_v2_old")
                self._conn.execute(_CREATE_META)
                self._conn.execute(_CREATE_JOBS)
                self._conn.execute(_CREATE_TRANSITIONS)
                self._conn.execute(_CREATE_DEPENDENCIES)
                self._conn.execute(
                    "INSERT INTO jobs ("
                    "job_id, cluster_name, scheduler, root_job_id, attempt, "
                    "previous_attempt_job_id, retry_group_id, scheduler_job_id, "
                    "state, command_type, command_display, cwd, "
                    "submitted_at, started_at, finished_at, last_polled, "
                    "exit_code, failure_reason, metadata, request_json, profile_name, cleaned_at) "
                    "SELECT job_id, cluster_name, scheduler, job_id, 1, "
                    "NULL, job_id, scheduler_job_id, "
                    "state, command_type, command_display, cwd, "
                    "submitted_at, started_at, finished_at, last_polled, "
                    "exit_code, failure_reason, metadata, '{}', NULL, NULL "
                    "FROM _jobs_v2_old"
                )
                self._conn.execute("DROP TABLE _jobs_v2_old")
                self._conn.execute(_CREATE_ALLOCATIONS)
                self._conn.execute(_CREATE_IDX_CLUSTER_STATE)
                self._conn.execute(_CREATE_IDX_TRANSITIONS)
                self._conn.execute(_CREATE_IDX_ROOT_ATTEMPT)
                self._conn.execute(_CREATE_IDX_RETRY_GROUP)
                self._conn.execute(_CREATE_IDX_DEPENDENCIES)
                self._conn.execute(_CREATE_IDX_ALLOCATIONS)
                self._conn.execute(
                    "INSERT OR REPLACE INTO molq_meta (key, value) VALUES (?, ?)",
                    ("schema_version", _SCHEMA_VERSION),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def _migrate_v3plus_to_current(self) -> None:
        with self._write_lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                columns = {
                    row["name"]
                    for row in self._conn.execute("PRAGMA table_info(jobs)").fetchall()
                }
                if "root_job_id" not in columns:
                    self._conn.execute(
                        "ALTER TABLE jobs ADD COLUMN root_job_id TEXT NOT NULL DEFAULT ''"
                    )
                if "attempt" not in columns:
                    self._conn.execute(
                        "ALTER TABLE jobs ADD COLUMN attempt INTEGER NOT NULL DEFAULT 1"
                    )
                if "previous_attempt_job_id" not in columns:
                    self._conn.execute(
                        "ALTER TABLE jobs ADD COLUMN previous_attempt_job_id TEXT"
                    )
                if "retry_group_id" not in columns:
                    self._conn.execute(
                        "ALTER TABLE jobs ADD COLUMN retry_group_id TEXT"
                    )
                if "request_json" not in columns:
                    self._conn.execute(
                        "ALTER TABLE jobs ADD COLUMN request_json TEXT DEFAULT '{}'"
                    )
                if "profile_name" not in columns:
                    self._conn.execute("ALTER TABLE jobs ADD COLUMN profile_name TEXT")
                if "cleaned_at" not in columns:
                    self._conn.execute("ALTER TABLE jobs ADD COLUMN cleaned_at REAL")

                self._conn.execute(
                    "UPDATE jobs SET root_job_id = job_id WHERE root_job_id = '' OR root_job_id IS NULL"
                )
                self._conn.execute(
                    "UPDATE jobs SET retry_group_id = root_job_id WHERE retry_group_id IS NULL"
                )
                self._conn.execute(_CREATE_DEPENDENCIES)
                self._conn.execute(_CREATE_ALLOCATIONS)
                self._conn.execute(_CREATE_IDX_CLUSTER_STATE)
                self._conn.execute(_CREATE_IDX_TRANSITIONS)
                self._conn.execute(_CREATE_IDX_ROOT_ATTEMPT)
                self._conn.execute(_CREATE_IDX_RETRY_GROUP)
                self._conn.execute(_CREATE_IDX_DEPENDENCIES)
                self._conn.execute(_CREATE_IDX_ALLOCATIONS)
                self._conn.execute(
                    "INSERT OR REPLACE INTO molq_meta (key, value) VALUES (?, ?)",
                    ("schema_version", _SCHEMA_VERSION),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def _create_schema(self) -> None:
        """Create all tables and indexes for the current schema."""
        with self._write_lock:
            self._conn.execute(_CREATE_META)
            self._conn.execute(
                "INSERT OR REPLACE INTO molq_meta (key, value) VALUES (?, ?)",
                ("schema_version", _SCHEMA_VERSION),
            )
            self._conn.execute(_CREATE_JOBS)
            self._conn.execute(_CREATE_TRANSITIONS)
            self._conn.execute(_CREATE_DEPENDENCIES)
            self._conn.execute(_CREATE_ALLOCATIONS)
            self._conn.execute(_CREATE_IDX_CLUSTER_STATE)
            self._conn.execute(_CREATE_IDX_TRANSITIONS)
            self._conn.execute(_CREATE_IDX_ROOT_ATTEMPT)
            self._conn.execute(_CREATE_IDX_RETRY_GROUP)
            self._conn.execute(_CREATE_IDX_DEPENDENCIES)
            self._conn.execute(_CREATE_IDX_ALLOCATIONS)
            self._conn.commit()
