"""Tests for molq.store — JobStore SQLite persistence."""

import sqlite3
import threading
import time
from pathlib import Path

import pytest

from molq.errors import StoreError
from molq.models import Command, JobDependency, JobSpec, RememberedAllocation
from molq.status import JobState
from molq.store import JobStore
from molq.types import JobScheduling


@pytest.fixture
def file_store(tmp_path):
    store = JobStore(tmp_path / "test.db")
    yield store
    store.close()


def _make_spec(job_id: str = "test-id", cluster: str = "dev") -> JobSpec:
    return JobSpec(
        job_id=job_id,
        cluster_name=cluster,
        scheduler="local",
        command=Command.from_submit_args(argv=["echo", "hello"]),
    )


class TestSchemaCreation:
    def test_creates_tables(self, memory_store: JobStore):
        rows = memory_store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = {r["name"] for r in rows}
        assert "molq_meta" in names
        assert "jobs" in names
        assert "job_dependencies" in names
        assert "status_transitions" in names

    def test_schema_version(self, memory_store: JobStore):
        row = memory_store._conn.execute(
            "SELECT value FROM molq_meta WHERE key = 'schema_version'"
        ).fetchone()
        assert row["value"] == "8"

    def test_file_backed(self, file_store: JobStore):
        assert isinstance(file_store.db_path, Path)
        assert file_store.db_path.exists()


class TestInsertAndGet:
    def test_insert_and_get(self, memory_store: JobStore):
        spec = _make_spec()
        memory_store.insert_job(spec)

        record = memory_store.get_record("test-id")
        assert record is not None
        assert record.job_id == "test-id"
        assert record.cluster_name == "dev"
        assert record.scheduler == "local"
        assert record.state == JobState.CREATED
        assert record.command_type == "argv"
        assert record.command_display == "echo hello"

    def test_get_nonexistent(self, memory_store: JobStore):
        assert memory_store.get_record("nope") is None

    def test_initial_transition_recorded(self, memory_store: JobStore):
        spec = _make_spec()
        memory_store.insert_job(spec)

        rows = memory_store._conn.execute(
            "SELECT * FROM status_transitions WHERE job_id = ?",
            ("test-id",),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["new_state"] == "created"
        assert rows[0]["old_state"] is None

    def test_duplicate_job_id_raises(self, memory_store: JobStore):
        spec = _make_spec()
        memory_store.insert_job(spec)
        with pytest.raises(sqlite3.IntegrityError):
            memory_store.insert_job(spec)


class TestUpdateJob:
    def test_update_state(self, memory_store: JobStore):
        memory_store.insert_job(_make_spec())
        memory_store.update_job("test-id", state=JobState.SUBMITTED)

        record = memory_store.get_record("test-id")
        assert record.state == JobState.SUBMITTED

    def test_update_scheduler_job_id(self, memory_store: JobStore):
        memory_store.insert_job(_make_spec())
        memory_store.update_job("test-id", scheduler_job_id="12345")

        record = memory_store.get_record("test-id")
        assert record.scheduler_job_id == "12345"

    def test_update_multiple_fields(self, memory_store: JobStore):
        memory_store.insert_job(_make_spec())
        memory_store.update_job(
            "test-id",
            state=JobState.SUCCEEDED,
            exit_code=0,
            finished_at=1000.0,
        )
        record = memory_store.get_record("test-id")
        assert record.state == JobState.SUCCEEDED
        assert record.exit_code == 0
        assert record.finished_at == 1000.0

    def test_update_noop(self, memory_store: JobStore):
        memory_store.insert_job(_make_spec())
        # No fields provided — should not raise
        memory_store.update_job("test-id")


class TestRecordTransition:
    def test_transition(self, memory_store: JobStore):
        memory_store.insert_job(_make_spec())
        memory_store.record_transition(
            "test-id",
            old_state=JobState.CREATED,
            new_state=JobState.SUBMITTED,
            timestamp=time.time() + 1,
            reason="submitted to scheduler",
        )

        rows = memory_store._conn.execute(
            "SELECT * FROM status_transitions WHERE job_id = ? ORDER BY timestamp",
            ("test-id",),
        ).fetchall()
        assert len(rows) == 2  # creation + this one
        assert rows[1]["old_state"] == "created"
        assert rows[1]["new_state"] == "submitted"
        assert rows[1]["reason"] == "submitted to scheduler"

    def test_get_transitions(self, memory_store: JobStore):
        memory_store.insert_job(_make_spec())
        memory_store.record_transition(
            "test-id",
            old_state=JobState.CREATED,
            new_state=JobState.SUBMITTED,
            timestamp=time.time() + 1,
            reason="submitted to scheduler",
        )

        transitions = memory_store.get_transitions("test-id")
        assert len(transitions) == 2
        assert transitions[0].new_state == JobState.CREATED
        assert transitions[1].new_state == JobState.SUBMITTED


class TestListRecords:
    def test_list_active_only(self, memory_store: JobStore):
        memory_store.insert_job(_make_spec("j1"))
        memory_store.insert_job(_make_spec("j2"))
        memory_store.update_job("j2", state=JobState.SUCCEEDED)

        records = memory_store.list_records("dev", include_terminal=False)
        assert len(records) == 1
        assert records[0].job_id == "j1"

    def test_list_including_terminal(self, memory_store: JobStore):
        memory_store.insert_job(_make_spec("j1"))
        memory_store.insert_job(_make_spec("j2"))
        memory_store.update_job("j2", state=JobState.SUCCEEDED)

        records = memory_store.list_records("dev", include_terminal=True)
        assert len(records) == 2

    def test_list_by_cluster(self, memory_store: JobStore):
        memory_store.insert_job(_make_spec("j1", "dev"))
        memory_store.insert_job(_make_spec("j2", "prod"))

        records = memory_store.list_records("dev", include_terminal=True)
        assert len(records) == 1
        assert records[0].cluster_name == "dev"

    def test_get_active_records(self, memory_store: JobStore):
        memory_store.insert_job(_make_spec("j1"))
        memory_store.insert_job(_make_spec("j2"))
        memory_store.update_job("j1", state=JobState.RUNNING)
        memory_store.update_job("j2", state=JobState.FAILED)

        active = memory_store.get_active_records("dev")
        assert len(active) == 1
        assert active[0].job_id == "j1"


class TestDependencies:
    def test_get_dependents(self, memory_store: JobStore):
        memory_store.insert_job(_make_spec("parent"))
        memory_store.insert_job(_make_spec("child"))
        memory_store.add_dependencies(
            "child",
            [
                JobDependency(
                    job_id="child",
                    dependency_job_id="parent",
                    dependency_type="after_success",
                    scheduler_dependency="afterok:123",
                )
            ],
        )

        dependents = memory_store.get_dependents("parent")
        assert len(dependents) == 1
        assert dependents[0].job_id == "child"

    def test_get_dependency_previews(self, memory_store: JobStore):
        memory_store.insert_job(_make_spec("parent"))
        memory_store.insert_job(_make_spec("child"))
        memory_store.update_job("parent", state=JobState.SUCCEEDED, started_at=10.0)
        memory_store.add_dependencies(
            "child",
            [
                JobDependency(
                    job_id="child",
                    dependency_job_id="parent",
                    dependency_type="after_success",
                    scheduler_dependency="afterok:123",
                )
            ],
        )

        previews = memory_store.get_dependency_previews(["parent", "child"])

        assert previews["child"].upstream_total == 1
        assert previews["child"].upstream_satisfied == 1
        assert previews["child"].upstream[0].relation_state == "satisfied"
        assert previews["parent"].downstream_total == 1
        assert previews["parent"].downstream[0].job_id == "child"


class TestMigration:
    def test_v1_database_backed_up(self, tmp_path: Path):
        db_path = tmp_path / "jobs.db"
        # Create a v1-style database (has jobs table but no molq_meta)
        conn = sqlite3.connect(str(db_path))
        conn.execute("""CREATE TABLE jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section TEXT NOT NULL,
                job_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending'
            )""")
        conn.execute(
            "INSERT INTO jobs (section, job_id, status) VALUES (?, ?, ?)",
            ("old", 1, "pending"),
        )
        conn.commit()
        conn.close()

        # Open with new JobStore — should backup and recreate
        store = JobStore(db_path)
        try:
            backup = tmp_path / "jobs.db.v1.bak"
            assert backup.exists()

            # New schema should work
            spec = _make_spec()
            store.insert_job(spec)
            record = store.get_record("test-id")
            assert record is not None
        finally:
            store.close()

    def test_future_version_raises(self, tmp_path: Path):
        db_path = tmp_path / "jobs.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE molq_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute("INSERT INTO molq_meta VALUES ('schema_version', '99')")
        conn.commit()
        conn.close()

        with pytest.raises(StoreError, match="newer"):
            JobStore(db_path)


class TestConcurrency:
    def test_concurrent_writes(self, tmp_path: Path):
        store = JobStore(tmp_path / "concurrent.db")
        errors: list[Exception] = []

        def insert_job(idx: int) -> None:
            try:
                spec = _make_spec(f"job-{idx}")
                store.insert_job(spec)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=insert_job, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors during concurrent writes: {errors}"

        records = store.list_records("dev", include_terminal=True)
        assert len(records) == 20
        store.close()


class TestAllocationMemory:
    """Persisted, retention-independent memory of used scheduling configs."""

    def test_allocations_table_created(self, memory_store: JobStore):
        rows = memory_store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='allocations'"
        ).fetchall()
        assert len(rows) == 1

    def test_record_first_use(self, memory_store: JobStore):
        memory_store.record_allocation(
            "hpc",
            JobScheduling(partition="main", account="proj1", qos="normal"),
            now=100.0,
        )
        got = memory_store.list_allocations("hpc")
        assert len(got) == 1
        alloc = got[0]
        assert isinstance(alloc, RememberedAllocation)
        assert (alloc.partition, alloc.account, alloc.qos) == (
            "main",
            "proj1",
            "normal",
        )
        assert alloc.use_count == 1
        assert alloc.last_used == 100.0

    def test_record_same_identity_bumps_count(self, memory_store: JobStore):
        sched = JobScheduling(partition="main", account="proj1")
        memory_store.record_allocation("hpc", sched, now=100.0)
        memory_store.record_allocation("hpc", sched, now=200.0)
        got = memory_store.list_allocations("hpc")
        assert len(got) == 1
        assert got[0].use_count == 2
        assert got[0].last_used == 200.0

    def test_nullable_fields_distinct_identities(self, memory_store: JobStore):
        # None in different positions must not collide via NULL ambiguity.
        memory_store.record_allocation("hpc", JobScheduling(partition="main"), now=1.0)
        memory_store.record_allocation("hpc", JobScheduling(account="main"), now=2.0)
        memory_store.record_allocation(
            "hpc", JobScheduling(partition="main", account="main"), now=3.0
        )
        got = memory_store.list_allocations("hpc")
        assert len(got) == 3
        assert all(a.use_count == 1 for a in got)

    def test_list_ordered_by_recency_with_limit(self, memory_store: JobStore):
        memory_store.record_allocation("hpc", JobScheduling(partition="a"), now=10.0)
        memory_store.record_allocation("hpc", JobScheduling(partition="b"), now=30.0)
        memory_store.record_allocation("hpc", JobScheduling(partition="c"), now=20.0)
        got = memory_store.list_allocations("hpc", limit=2)
        assert [a.partition for a in got] == ["b", "c"]

    def test_scoped_by_cluster(self, memory_store: JobStore):
        memory_store.record_allocation("hpc", JobScheduling(partition="a"), now=1.0)
        memory_store.record_allocation("other", JobScheduling(partition="b"), now=2.0)
        assert [a.partition for a in memory_store.list_allocations("hpc")] == ["a"]

    def test_all_none_scheduling_not_recorded(self, memory_store: JobStore):
        memory_store.record_allocation("hpc", JobScheduling(), now=1.0)
        assert memory_store.list_allocations("hpc") == []

    def test_migration_v7_to_v8_preserves_jobs(self, tmp_path: Path):
        # Build a current-schema DB, then simulate a v7 DB (no allocations
        # table, version pinned to "7") and reopen to exercise the migration.
        db = tmp_path / "mig.db"
        store = JobStore(db)
        store.insert_job(_make_spec("keep-me", "hpc"))
        store._conn.execute("DROP TABLE allocations")
        store._conn.execute(
            "UPDATE molq_meta SET value = '7' WHERE key = 'schema_version'"
        )
        store._conn.commit()
        store.close()

        reopened = JobStore(db)
        version = reopened._conn.execute(
            "SELECT value FROM molq_meta WHERE key = 'schema_version'"
        ).fetchone()["value"]
        assert version == "8"
        tables = {
            r["name"]
            for r in reopened._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "allocations" in tables
        assert reopened.get_record("keep-me") is not None
        reopened.close()

    def test_remembered_allocation_is_public_export(self):
        # AC-1: importable from the molq top-level package, not just molq.models.
        import molq

        assert molq.RememberedAllocation is RememberedAllocation

    def test_retention_deletes_jobs_keeps_allocations(self, tmp_path: Path):
        # AC-9: pruning terminal job rows must not touch remembered allocations.
        store = JobStore(tmp_path / "ret.db")
        store.insert_job(_make_spec("doomed", "hpc"))
        store.record_allocation("hpc", JobScheduling(partition="main"), now=1.0)

        store.delete_terminal_records(["doomed"])

        assert store.get_record("doomed") is None
        survived = store.list_allocations("hpc")
        assert len(survived) == 1
        assert survived[0].partition == "main"
        store.close()
