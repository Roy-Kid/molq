"""Tests for molq.cli.main — CLI commands."""

import shutil
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from molq.cli.main import app
from molq.models import (
    JobDependency,
    JobRecord,
    RememberedAllocation,
    StatusTransition,
)
from molq.status import JobState
from molq.transport import LocalTransport

runner = CliRunner()


@pytest.fixture
def mock_submitor():
    m = MagicMock()
    m.cluster_name = "cli_local"
    return m


class TestSubmitCommand:
    @patch("molq.cli._helpers.open_submitor")
    def test_submit_basic(self, mock_create):
        handle = MagicMock()
        handle.job_id = "test-id"
        handle.scheduler_job_id = "12345"

        mock_submitor = MagicMock()
        mock_submitor.submit_job.return_value = handle
        mock_create.return_value.__enter__.return_value = mock_submitor

        result = runner.invoke(app, ["submit", "local", "echo", "hello"])
        assert result.exit_code == 0
        assert "Job submitted" in result.output

    def test_submit_no_command(self):
        result = runner.invoke(app, ["submit", "local"])
        assert result.exit_code == 1


class TestListCommand:
    @patch("molq.cli._helpers.open_submitor")
    def test_list_empty(self, mock_create):
        mock_submitor = MagicMock()
        mock_submitor.list_jobs.return_value = []
        mock_create.return_value.__enter__.return_value = mock_submitor

        result = runner.invoke(app, ["list", "local"])
        assert result.exit_code == 0
        assert "No jobs" in result.output

    @patch("molq.cli._helpers.open_submitor")
    def test_list_with_jobs(self, mock_create):
        record = JobRecord(
            job_id="abc-123",
            cluster_name="cli_local",
            scheduler="local",
            state=JobState.RUNNING,
            command_type="argv",
            command_display="echo hello",
        )
        mock_submitor = MagicMock()
        mock_submitor.list_jobs.return_value = [record]
        mock_create.return_value.__enter__.return_value = mock_submitor

        result = runner.invoke(app, ["list", "local"])
        assert result.exit_code == 0
        assert "abc-123" in result.output


class TestStatusCommand:
    @patch("molq.cli._helpers.open_submitor")
    def test_status_found(self, mock_create):
        record = JobRecord(
            job_id="abc-123",
            cluster_name="cli_local",
            scheduler="local",
            state=JobState.RUNNING,
            command_type="argv",
            command_display="echo hello",
        )
        mock_submitor = MagicMock()
        mock_submitor.get_job.return_value = record
        mock_create.return_value.__enter__.return_value = mock_submitor

        result = runner.invoke(app, ["status", "abc-123", "local"])
        assert result.exit_code == 0
        assert "running" in result.output

    @patch("molq.cli._helpers.open_submitor")
    def test_status_not_found(self, mock_create):
        from molq.errors import JobNotFoundError

        mock_submitor = MagicMock()
        mock_submitor.get_job.side_effect = JobNotFoundError("abc")
        mock_create.return_value.__enter__.return_value = mock_submitor

        result = runner.invoke(app, ["status", "abc", "local"])
        assert result.exit_code == 1
        assert "not found" in result.output


class TestLogsCommand:
    @patch("molq.cli._helpers.open_submitor")
    def test_logs_stdout(self, mock_create, tmp_path):
        log_path = tmp_path / "stdout.log"
        log_path.write_text("line1\nline2\n")
        record = JobRecord(
            job_id="abc-123",
            cluster_name="cli_local",
            scheduler="local",
            state=JobState.RUNNING,
            command_type="argv",
            command_display="echo hello",
            metadata={"molq.stdout_path": str(log_path)},
        )
        mock_submitor = MagicMock()
        mock_submitor.get_job.return_value = record
        # Real transport: log paths live on the cluster filesystem, so the
        # command resolves and reads them through it.
        mock_submitor.target.transport = LocalTransport()
        mock_create.return_value.__enter__.return_value = mock_submitor

        result = runner.invoke(app, ["logs", "abc-123", "local", "--tail", "1"])
        assert result.exit_code == 0
        assert "line2" in result.output

    @patch("molq.cli._helpers.open_submitor")
    def test_logs_both(self, mock_create, tmp_path):
        stdout_path = tmp_path / "stdout.log"
        stderr_path = tmp_path / "stderr.log"
        stdout_path.write_text("out\n")
        stderr_path.write_text("err\n")
        record = JobRecord(
            job_id="abc-123",
            cluster_name="cli_local",
            scheduler="local",
            state=JobState.SUCCEEDED,
            command_type="argv",
            command_display="echo hello",
            metadata={
                "molq.stdout_path": str(stdout_path),
                "molq.stderr_path": str(stderr_path),
            },
        )
        mock_submitor = MagicMock()
        mock_submitor.get_job.return_value = record
        # Real transport: log paths live on the cluster filesystem, so the
        # command resolves and reads them through it.
        mock_submitor.target.transport = LocalTransport()
        mock_create.return_value.__enter__.return_value = mock_submitor

        result = runner.invoke(app, ["logs", "abc-123", "local", "--stream", "both"])
        assert result.exit_code == 0
        assert "[stdout] out" in result.output
        assert "[stderr] err" in result.output

    @patch("molq.cli._helpers.open_submitor")
    def test_logs_follow(self, mock_create, tmp_path):
        stdout_path = tmp_path / "stdout.log"
        stdout_path.write_text("line1\n")
        record = JobRecord(
            job_id="abc-123",
            cluster_name="cli_local",
            scheduler="local",
            state=JobState.SUCCEEDED,
            command_type="argv",
            command_display="echo hello",
            metadata={"molq.stdout_path": str(stdout_path)},
        )
        mock_submitor = MagicMock()
        mock_submitor.get_job.return_value = record
        # Real transport: log paths live on the cluster filesystem, so the
        # command resolves and reads them through it.
        mock_submitor.target.transport = LocalTransport()
        mock_create.return_value.__enter__.return_value = mock_submitor

        result = runner.invoke(app, ["logs", "abc-123", "local", "--follow"])
        assert result.exit_code == 0
        assert "line1" in result.output


class TestHistoryAndInspect:
    @patch("molq.cli._helpers.open_submitor")
    def test_history(self, mock_create):
        record = JobRecord(
            job_id="abc-123",
            cluster_name="cli_local",
            scheduler="local",
            state=JobState.FAILED,
            scheduler_job_id="12345",
            command_type="argv",
            command_display="echo hello",
        )
        mock_submitor = MagicMock()
        mock_submitor.list_jobs.return_value = [record]
        mock_create.return_value.__enter__.return_value = mock_submitor

        result = runner.invoke(app, ["history", "local", "--all"])
        assert result.exit_code == 0
        assert "History" in result.output
        assert "failed" in result.output

    @patch("molq.cli._helpers.open_submitor")
    def test_inspect(self, mock_create):
        record = JobRecord(
            job_id="abc-123",
            cluster_name="cli_local",
            scheduler="local",
            state=JobState.RUNNING,
            scheduler_job_id="12345",
            cwd="/tmp/work",
            command_type="argv",
            command_display="echo hello",
            metadata={
                "molq.job_dir": "/tmp/jobs/abc-123",
                "molq.stdout_path": "/tmp/jobs/abc-123/stdout.log",
                "molq.stderr_path": "/tmp/jobs/abc-123/stderr.log",
            },
        )
        transitions = [
            StatusTransition(
                job_id="abc-123",
                old_state=None,
                new_state=JobState.CREATED,
                timestamp=1.0,
                reason="job created",
            ),
            StatusTransition(
                job_id="abc-123",
                old_state=JobState.CREATED,
                new_state=JobState.SUBMITTED,
                timestamp=2.0,
                reason="submitted",
            ),
        ]
        mock_submitor = MagicMock()
        mock_submitor.get_job.return_value = record
        mock_submitor.get_transitions.return_value = transitions
        mock_submitor.get_retry_family.return_value = [record]
        mock_submitor.get_dependencies.return_value = [
            JobDependency(
                job_id="abc-123",
                dependency_job_id="dep-1",
                dependency_type="after_success",
                scheduler_dependency="afterok:999",
            )
        ]
        mock_submitor.get_dependents.return_value = []
        mock_create.return_value.__enter__.return_value = mock_submitor

        result = runner.invoke(app, ["inspect", "abc-123", "local"])
        assert result.exit_code == 0
        assert "Scheduler ID:   12345" in result.output
        assert "Retry Family:" in result.output
        assert "Dependencies:" in result.output
        assert "Upstream:" in result.output
        assert "Downstream:" in result.output
        assert "Timeline:" in result.output
        assert "created" in result.output


class TestCancelCommand:
    @patch("molq.cli._helpers.open_submitor")
    def test_cancel_success(self, mock_create):
        mock_submitor = MagicMock()
        mock_create.return_value.__enter__.return_value = mock_submitor

        result = runner.invoke(app, ["cancel", "abc-123", "local"])
        assert result.exit_code == 0
        assert "cancelled" in result.output

    @patch("molq.cli._helpers.open_submitor")
    def test_cancel_not_found(self, mock_create):
        from molq.errors import JobNotFoundError

        mock_submitor = MagicMock()
        mock_submitor.cancel_job.side_effect = JobNotFoundError("abc")
        mock_create.return_value.__enter__.return_value = mock_submitor

        result = runner.invoke(app, ["cancel", "abc", "local"])
        assert result.exit_code == 1


class TestMaintenanceCommands:
    @patch("molq.cli._helpers.open_submitor")
    def test_cleanup(self, mock_create):
        mock_submitor = MagicMock()
        mock_submitor.cleanup_jobs.return_value = {
            "job_dirs": ["/tmp/jobs/a"],
            "records": ["job-1"],
        }
        mock_create.return_value.__enter__.return_value = mock_submitor

        result = runner.invoke(app, ["cleanup", "local", "--dry-run"])
        assert result.exit_code == 0
        assert "Job dirs: 1" in result.output
        assert "record: job-1" in result.output

    @patch("molq.cli._helpers.open_submitor")
    def test_daemon_once(self, mock_create):
        mock_submitor = MagicMock()
        mock_create.return_value.__enter__.return_value = mock_submitor

        result = runner.invoke(app, ["daemon", "local", "--once"])
        assert result.exit_code == 0
        mock_submitor.run_daemon.assert_called_once()


@pytest.mark.skip(reason="allocations CLI not wired on master yet")
class TestAllocationsCommand:
    @patch("molq.cli._helpers.open_submitor")
    def test_allocations_empty(self, mock_create):
        mock_submitor = MagicMock()
        mock_submitor.remembered_allocations.return_value = []
        mock_create.return_value.__enter__.return_value = mock_submitor

        result = runner.invoke(app, ["allocations", "slurm"])
        assert result.exit_code == 0
        assert "No remembered allocations" in result.output

    @patch("molq.cli._helpers.open_submitor")
    def test_allocations_with_rows(self, mock_create):
        alloc = RememberedAllocation(
            partition="gpu",
            account="proj1",
            qos="high",
            reservation=None,
            label=None,
            last_used=1_700_000_000.0,
            use_count=4,
        )
        mock_submitor = MagicMock()
        mock_submitor.remembered_allocations.return_value = [alloc]
        mock_create.return_value.__enter__.return_value = mock_submitor

        result = runner.invoke(app, ["allocations", "slurm"])
        assert result.exit_code == 0
        assert "gpu" in result.output
        assert "proj1" in result.output
        assert "high" in result.output
        assert "4" in result.output


class TestDestinationResolution:
    """The CLI must never invent an SSH transport for a name that is not a
    real ``Host`` alias.

    Regression for v0.6.0: ``_open_submitor`` optimistically called
    ``Cluster.from_ssh_alias(...)``, and ``ssh -G`` succeeds for *any*
    string, so the default namespace ``cli_local`` produced an
    ``SshTransport`` pointed at a nonexistent host. Every job command then
    failed with ``remote mkdir failed``.

    These tests exercise the real ``_open_submitor`` — deliberately not
    mocked, unlike the command tests above.
    """

    @pytest.fixture
    def isolated_home(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        (home / ".ssh").mkdir(parents=True)
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("MOLCRAFTS_HOME", str(tmp_path / "molcrafts"))
        return home

    def test_default_namespace_stays_local(self, isolated_home):
        from molq.cli._app import SchedulerType
        from molq.cli._helpers import open_submitor
        from molq.transport import LocalTransport

        with open_submitor(SchedulerType.local) as submitor:
            assert isinstance(submitor.target.transport, LocalTransport)
            assert submitor.cluster_name == "cli_local"

    def test_unknown_cluster_name_stays_local(self, isolated_home):
        from molq.cli._app import SchedulerType
        from molq.cli._helpers import open_submitor
        from molq.transport import LocalTransport

        with open_submitor(SchedulerType.slurm, cluster="not-an-ssh-host") as submitor:
            assert isinstance(submitor.target.transport, LocalTransport)
            assert submitor.cluster_name == "not-an-ssh-host"

    @pytest.mark.skipif(
        shutil.which("ssh") is None, reason="requires an OpenSSH client"
    )
    def test_configured_ssh_alias_uses_ssh_transport(self, isolated_home):
        (isolated_home / ".ssh" / "config").write_text(
            "Host testbox\n  HostName testbox.example.org\n  User alice\n"
        )
        from molq.cli._app import SchedulerType
        from molq.cli._helpers import open_submitor
        from molq.transport import SshTransport

        with open_submitor(SchedulerType.slurm, cluster="testbox") as submitor:
            assert isinstance(submitor.target.transport, SshTransport)
            assert submitor.cluster_name == "testbox"

    def test_submit_local_end_to_end(self, isolated_home, tmp_path):
        """The headline smoke test: `molq submit local echo hello` works."""
        workdir = tmp_path / "work"
        workdir.mkdir()
        result = runner.invoke(
            app,
            ["submit", "local", "--workdir", str(workdir), "echo", "hello"],
        )
        assert result.exit_code == 0, result.output
        assert "Job submitted" in result.output


class TestLogsOverRemoteTransport:
    """Log paths live on the cluster's filesystem, not the driver's.

    Before 0.7.0 the logs command called Path.exists()/open() on those paths
    locally, so every remote job reported a missing log.
    """

    @pytest.fixture
    def loopback_transport(self, tmp_path):
        """SshTransport whose ssh binary runs the command on this machine."""
        from molq.options import SshTransportOptions
        from molq.transport import SshTransport

        stub = tmp_path / "fake_ssh"
        stub.write_text(
            '#!/bin/sh\nfor a in "$@"; do cmd="$a"; done\nexec sh -c "$cmd"\n'
        )
        stub.chmod(0o755)
        return SshTransport(options=SshTransportOptions(host="h"), _ssh_bin=str(stub))

    def _record(self, stdout_path):
        return JobRecord(
            job_id="abc-123",
            cluster_name="dardel",
            scheduler="slurm",
            state=JobState.SUCCEEDED,
            command_type="argv",
            command_display="python train.py",
            metadata={"molq.stdout_path": str(stdout_path)},
        )

    @patch("molq.cli._helpers.open_submitor")
    def test_reads_log_through_transport(
        self, mock_create, loopback_transport, tmp_path
    ):
        log_path = tmp_path / "stdout.log"
        log_path.write_text("epoch 1\nepoch 2\n")

        mock_submitor = MagicMock()
        mock_submitor.get_job.return_value = self._record(log_path)
        mock_submitor.target.transport = loopback_transport
        mock_create.return_value.__enter__.return_value = mock_submitor

        result = runner.invoke(app, ["logs", "abc-123", "slurm"])
        assert result.exit_code == 0, result.output
        assert "epoch 2" in result.output

    @patch("molq.cli._helpers.open_submitor")
    def test_tail_is_evaluated_remotely(
        self, mock_create, loopback_transport, tmp_path
    ):
        log_path = tmp_path / "stdout.log"
        log_path.write_text("".join(f"line{i}\n" for i in range(100)))

        mock_submitor = MagicMock()
        mock_submitor.get_job.return_value = self._record(log_path)
        mock_submitor.target.transport = loopback_transport
        mock_create.return_value.__enter__.return_value = mock_submitor

        result = runner.invoke(app, ["logs", "abc-123", "slurm", "--tail", "2"])
        assert result.exit_code == 0, result.output
        assert "line99" in result.output
        assert "line0\n" not in result.output

    @patch("molq.cli._helpers.open_submitor")
    def test_missing_remote_log_reports_cleanly(
        self, mock_create, loopback_transport, tmp_path
    ):
        mock_submitor = MagicMock()
        mock_submitor.get_job.return_value = self._record(tmp_path / "absent.log")
        mock_submitor.target.transport = loopback_transport
        mock_create.return_value.__enter__.return_value = mock_submitor

        result = runner.invoke(app, ["logs", "abc-123", "slurm"])
        assert result.exit_code == 1
        assert "does not exist" in result.output


class TestVersionFlag:
    """`molq --version` answers the first question in any bug report."""

    def test_reports_installed_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert result.output.strip()

    def test_short_flag(self):
        assert runner.invoke(app, ["-V"]).exit_code == 0

    def test_does_not_require_a_subcommand(self):
        # is_eager: the callback fires before Typer demands a command.
        result = runner.invoke(app, ["--version"])
        assert "Usage:" not in result.output

    def test_bare_invocation_still_shows_help(self):
        result = runner.invoke(app, [])
        assert "submit" in result.output
