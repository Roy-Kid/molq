"""Tests for molq.artifacts — bringing a job's files back from the cluster."""

from __future__ import annotations

from pathlib import Path

import pytest

from molq.artifacts import fetch_job_dir, fetch_logs, local_scratch_dir
from molq.models import JobRecord
from molq.status import JobState
from molq.transport import LocalTransport


def _record(**metadata) -> JobRecord:
    return JobRecord(
        job_id="job-1",
        cluster_name="dev",
        scheduler="local",
        state=JobState.SUCCEEDED,
        metadata=metadata,
    )


class TestLocalScratchDir:
    def test_uses_jobs_dir_when_given(self, tmp_path):
        assert local_scratch_dir(tmp_path, "job-1", "logs") == (
            tmp_path / "job-1" / "logs"
        )

    def test_falls_back_to_cwd_not_the_job_cwd(self, tmp_path, monkeypatch):
        # The job's own cwd may name a directory on another machine.
        monkeypatch.chdir(tmp_path)
        assert local_scratch_dir(None, "job-1", "mirror") == (
            tmp_path / ".molq" / "fetched" / "job-1" / "mirror"
        )


class TestFetchLogs:
    def test_downloads_both_streams(self, tmp_path):
        remote = tmp_path / "remote"
        remote.mkdir()
        (remote / "out.log").write_text("stdout body\n")
        (remote / "err.log").write_text("stderr body\n")
        record = _record(
            **{
                "molq.stdout_path": str(remote / "out.log"),
                "molq.stderr_path": str(remote / "err.log"),
            }
        )

        result = fetch_logs(LocalTransport(), record, tmp_path / "dest")

        assert set(result) == {"stdout", "stderr"}
        assert result["stdout"].read_text() == "stdout body\n"
        assert result["stderr"].read_text() == "stderr body\n"

    def test_creates_destination(self, tmp_path):
        remote = tmp_path / "out.log"
        remote.write_text("x")
        record = _record(**{"molq.stdout_path": str(remote)})
        dest = tmp_path / "deep" / "nested" / "dest"

        fetch_logs(LocalTransport(), record, dest, streams=("stdout",))

        assert dest.is_dir()

    def test_unrecorded_stream_is_skipped(self, tmp_path):
        remote = tmp_path / "out.log"
        remote.write_text("x")
        record = _record(**{"molq.stdout_path": str(remote)})

        result = fetch_logs(LocalTransport(), record, tmp_path / "dest")

        assert set(result) == {"stdout"}

    def test_missing_remote_file_is_skipped(self, tmp_path):
        record = _record(**{"molq.stdout_path": str(tmp_path / "absent.log")})

        result = fetch_logs(LocalTransport(), record, tmp_path / "dest")

        assert result == {}

    def test_stream_subset_is_honored(self, tmp_path):
        (tmp_path / "out.log").write_text("o")
        (tmp_path / "err.log").write_text("e")
        record = _record(
            **{
                "molq.stdout_path": str(tmp_path / "out.log"),
                "molq.stderr_path": str(tmp_path / "err.log"),
            }
        )

        result = fetch_logs(
            LocalTransport(), record, tmp_path / "dest", streams=("stderr",)
        )

        assert set(result) == {"stderr"}


class TestFetchJobDir:
    def test_mirrors_the_directory(self, tmp_path):
        job_dir = tmp_path / "job"
        (job_dir / "sub").mkdir(parents=True)
        (job_dir / "result.txt").write_text("data")
        (job_dir / "sub" / "nested.txt").write_text("nested")
        record = _record(**{"molq.job_dir": str(job_dir)})

        dest = fetch_job_dir(LocalTransport(), record, tmp_path / "dest")

        assert (dest / "result.txt").read_text() == "data"
        assert (dest / "sub" / "nested.txt").read_text() == "nested"

    def test_exclude_is_applied(self, tmp_path):
        job_dir = tmp_path / "job"
        job_dir.mkdir()
        (job_dir / "keep.txt").write_text("keep")
        (job_dir / "skip.tmp").write_text("skip")
        record = _record(**{"molq.job_dir": str(job_dir)})

        dest = fetch_job_dir(
            LocalTransport(), record, tmp_path / "dest", exclude=("skip.tmp",)
        )

        assert (dest / "keep.txt").exists()
        assert not (dest / "skip.tmp").exists()

    def test_record_without_job_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="no recorded molq.job_dir"):
            fetch_job_dir(LocalTransport(), _record(), tmp_path / "dest")

    def test_returns_destination(self, tmp_path):
        job_dir = tmp_path / "job"
        job_dir.mkdir()
        (job_dir / "f").write_text("x")
        record = _record(**{"molq.job_dir": str(job_dir)})

        dest = fetch_job_dir(LocalTransport(), record, tmp_path / "dest")

        assert isinstance(dest, Path)
        assert dest == tmp_path / "dest"
