"""Tests for molq.retention — applying a retention policy."""

from __future__ import annotations

import pytest

from molq.models import Command, JobSpec, RetentionPolicy
from molq.retention import apply_retention
from molq.status import JobState
from molq.store import JobStore

DAY = 86400


@pytest.fixture
def store():
    s = JobStore(":memory:")
    yield s
    s.close()


def _finished_job(store, tmp_path, job_id, *, state, age_days, now):
    """Insert a terminal job whose job_dir exists on disk."""
    job_dir = tmp_path / job_id
    job_dir.mkdir()
    (job_dir / "stdout.log").write_text("output\n")
    store.insert_job(
        JobSpec(
            job_id=job_id,
            cluster_name="dev",
            scheduler="local",
            command=Command.from_submit_args(argv=["echo", "hi"]),
            metadata={"molq.job_dir": str(job_dir)},
        )
    )
    store.update_job(job_id, state=state, finished_at=now - age_days * DAY)
    return job_dir


class TestApplyRetention:
    def test_removes_expired_job_dir_and_record(self, store, tmp_path):
        now = 2_000_000_000.0
        job_dir = _finished_job(
            store, tmp_path, "old", state=JobState.SUCCEEDED, age_days=100, now=now
        )

        result = apply_retention(
            store, "dev", RetentionPolicy(), now=now, dry_run=False
        )

        assert result["job_dirs"] == [str(job_dir)]
        assert result["records"] == ["old"]
        assert not job_dir.exists()
        assert store.get_record("old") is None

    def test_keeps_fresh_jobs(self, store, tmp_path):
        now = 2_000_000_000.0
        job_dir = _finished_job(
            store, tmp_path, "fresh", state=JobState.SUCCEEDED, age_days=1, now=now
        )

        result = apply_retention(store, "dev", RetentionPolicy(), now=now)

        assert result == {"job_dirs": [], "records": []}
        assert job_dir.exists()
        assert store.get_record("fresh") is not None

    def test_dry_run_reports_without_deleting(self, store, tmp_path):
        now = 2_000_000_000.0
        job_dir = _finished_job(
            store, tmp_path, "old", state=JobState.SUCCEEDED, age_days=100, now=now
        )

        result = apply_retention(store, "dev", RetentionPolicy(), now=now, dry_run=True)

        assert result["job_dirs"] == [str(job_dir)]
        assert result["records"] == ["old"]
        # Nothing actually went.
        assert job_dir.exists()
        assert store.get_record("old") is not None

    def test_dirs_expire_before_records(self, store, tmp_path):
        """Between the two cutoffs, the files go but the history stays."""
        now = 2_000_000_000.0
        job_dir = _finished_job(
            store, tmp_path, "mid", state=JobState.SUCCEEDED, age_days=45, now=now
        )

        result = apply_retention(store, "dev", RetentionPolicy(), now=now)

        assert result["job_dirs"] == [str(job_dir)]
        assert result["records"] == []
        assert not job_dir.exists()
        assert store.get_record("mid") is not None

    def test_failed_job_dirs_are_kept_by_default(self, store, tmp_path):
        now = 2_000_000_000.0
        failed_dir = _finished_job(
            store, tmp_path, "bad", state=JobState.FAILED, age_days=45, now=now
        )

        result = apply_retention(store, "dev", RetentionPolicy(), now=now)

        assert result["job_dirs"] == []
        assert failed_dir.exists()

    def test_failed_job_dirs_go_when_policy_says_so(self, store, tmp_path):
        now = 2_000_000_000.0
        failed_dir = _finished_job(
            store, tmp_path, "bad", state=JobState.FAILED, age_days=45, now=now
        )

        result = apply_retention(
            store,
            "dev",
            RetentionPolicy(keep_failed_job_dirs=False),
            now=now,
        )

        assert result["job_dirs"] == [str(failed_dir)]
        assert not failed_dir.exists()

    def test_cleaned_dirs_are_not_reported_twice(self, store, tmp_path):
        now = 2_000_000_000.0
        _finished_job(
            store, tmp_path, "old", state=JobState.SUCCEEDED, age_days=45, now=now
        )

        first = apply_retention(store, "dev", RetentionPolicy(), now=now)
        second = apply_retention(store, "dev", RetentionPolicy(), now=now)

        assert first["job_dirs"] != []
        assert second["job_dirs"] == []

    def test_missing_directory_does_not_abort_the_sweep(self, store, tmp_path):
        """A dir removed by hand must not stop later jobs from being cleaned."""
        now = 2_000_000_000.0
        gone = _finished_job(
            store, tmp_path, "gone", state=JobState.SUCCEEDED, age_days=100, now=now
        )
        _finished_job(
            store, tmp_path, "also-old", state=JobState.SUCCEEDED, age_days=100, now=now
        )
        import shutil

        shutil.rmtree(gone)

        result = apply_retention(store, "dev", RetentionPolicy(), now=now)

        assert len(result["job_dirs"]) == 2
        assert set(result["records"]) == {"gone", "also-old"}

    def test_other_clusters_are_untouched(self, store, tmp_path):
        now = 2_000_000_000.0
        store.insert_job(
            JobSpec(
                job_id="other",
                cluster_name="prod",
                scheduler="local",
                command=Command.from_submit_args(argv=["echo", "hi"]),
            )
        )
        store.update_job("other", state=JobState.SUCCEEDED, finished_at=now - 999 * DAY)

        result = apply_retention(store, "dev", RetentionPolicy(), now=now)

        assert result == {"job_dirs": [], "records": []}
        assert store.get_record("other") is not None

    def test_job_without_recorded_dir_is_skipped_for_artifacts(self, store, tmp_path):
        now = 2_000_000_000.0
        store.insert_job(
            JobSpec(
                job_id="nodir",
                cluster_name="dev",
                scheduler="local",
                command=Command.from_submit_args(argv=["echo", "hi"]),
            )
        )
        store.update_job("nodir", state=JobState.SUCCEEDED, finished_at=now - 100 * DAY)

        result = apply_retention(store, "dev", RetentionPolicy(), now=now)

        assert result["job_dirs"] == []
        assert result["records"] == ["nodir"]
