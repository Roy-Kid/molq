"""The no-batch-system backend: run the job through a plain shell."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from molq._log import get_logger
from molq.errors import ConfigError, SchedulerError
from molq.models import JobSpec
from molq.options import LocalSchedulerOptions
from molq.scheduler.base import (
    DependencyEdge,
    QueueEntry,
    SchedulerCapabilities,
    TerminalStatus,
)
from molq.scheduler.script import _render_job_script, _shell_quote
from molq.status import JobState
from molq.transport import LocalTransport, Transport, TransportError

logger = get_logger(__name__)

# How long submit() waits for the wrapper to publish the job pid, expressed as
# remote-side poll attempts.  250 * 0.02s = 5s, matching the previous
# client-side budget but costing a single round trip instead of one per poll.
_PID_WAIT_ATTEMPTS = 250
_PID_WAIT_INTERVAL = "0.02"


class ShellScheduler:
    """Run jobs via a plain shell on whatever the transport points at.

    The single "no batch system" backend.  ``ShellScheduler`` writes a wrapper
    script that backgrounds the user command, captures its pid into a sibling
    file, and writes the exit code on completion.  Polling reads those files
    via the transport instead of touching local OS state — so the same
    implementation drives both ``Cluster(scheduler="local")`` (pairing with
    :class:`~molq.transport.LocalTransport`) and ``Cluster(scheduler="local",
    host=...)`` (paired with :class:`~molq.transport.SshTransport` for "ssh
    into my workstation and run this").
    """

    def __init__(
        self,
        options: LocalSchedulerOptions | None = None,
        *,
        transport: Transport | None = None,
    ) -> None:
        self._opts = options or LocalSchedulerOptions()
        self._transport: Transport = transport or LocalTransport()

    def capabilities(self) -> SchedulerCapabilities:
        return SchedulerCapabilities(
            supports_cwd=True,
            supports_env=True,
            supports_output_file=True,
            supports_error_file=True,
            # job_name is purely metadata for the shell path — accept it so
            # callers like molexp's SubmitHandler can set it uniformly.
            supports_job_name=True,
        )

    def submit(self, spec: JobSpec, job_dir: Path) -> str:
        # Materialize the user script locally first (it may reference files
        # the user expects on disk).  Submitor is responsible for staging the
        # job_dir to the transport's filesystem before submit when the
        # transport is non-local.
        script_path = self._materialize_script(spec, job_dir)
        wrapper_path = job_dir / "_wrapper.sh"
        pid_path = job_dir / ".pid"
        exit_code_path = job_dir / ".exit_code"

        # The wrapper runs the user script in the background, records its
        # pid, waits for it, and stores the exit code.  We then daemonise the
        # wrapper itself so closing the ssh channel doesn't kill the job.
        cwd = spec.execution.cwd or spec.cwd
        env_lines = ""
        if spec.execution.env:
            env_lines = (
                "\n".join(
                    f"export {k}={_shell_quote(v)}"
                    for k, v in sorted(spec.execution.env.items())
                )
                + "\n"
            )
        cd_line = f"cd {_shell_quote(str(cwd))}\n" if cwd else ""

        out_redir = (
            f" > {_shell_quote(spec.execution.output_file)}"
            if spec.execution.output_file
            else " > /dev/null"
        )
        err_redir = (
            f" 2> {_shell_quote(spec.execution.error_file)}"
            if spec.execution.error_file
            else " 2> /dev/null"
        )

        wrapper = (
            f"#!/bin/bash\n"
            f"{env_lines}"
            f"{cd_line}"
            f"( bash {_shell_quote(str(script_path))}{out_redir}{err_redir} ) &\n"
            f"pid=$!\n"
            f"echo $pid > {_shell_quote(str(pid_path))}\n"
            f"wait $pid\n"
            f"echo $? > {_shell_quote(str(exit_code_path))}\n"
        )
        # Wrapper script lands on the transport's filesystem so that ssh-routed
        # ShellScheduler instances find it on the remote at the same path the
        # remote shell will see.
        self._transport.write_text(str(wrapper_path), wrapper, mode=0o700)

        # Launch the wrapper as a detached background process via the transport
        # and capture the pid the wrapper writes into .pid.  We also put the
        # wrapper itself into nohup + background so closing the ssh session
        # doesn't terminate it.
        #
        # The wait for .pid happens *inside* this one remote command on
        # purpose.  Polling it from Python would cost one round trip per
        # attempt — over SSH that was up to ~250 connections per submission.
        # `-s` (exists and non-empty) avoids reading a half-written pid.
        launch = (
            f"nohup bash {_shell_quote(str(wrapper_path))} "
            f"> /dev/null 2>&1 < /dev/null &\n"
            f"wrapper_pid=$!\n"
            f"for _ in $(seq 1 {_PID_WAIT_ATTEMPTS}); do\n"
            f"  if [ -s {_shell_quote(str(pid_path))} ]; then\n"
            f"    cat {_shell_quote(str(pid_path))}\n"
            f"    exit 0\n"
            f"  fi\n"
            f"  sleep {_PID_WAIT_INTERVAL}\n"
            f"done\n"
            # Fallback: the wrapper pid still identifies the job for
            # kill/poll purposes.
            f"echo $wrapper_pid\n"
        )
        try:
            result = self._transport.run(["bash", "-c", launch], timeout=30)
        except TransportError as e:
            raise SchedulerError(
                "shell submission failed",
                command=["bash", "-c", launch],
            ) from e
        if result.returncode != 0:
            raise SchedulerError(
                "shell submission failed",
                stderr=result.stderr,
                command=["bash", "-c", launch],
            )
        # stdout is the inner job pid (what users see in `ps`), or the wrapper
        # pid if .pid never materialised.  Either identifies the job.
        return result.stdout.strip()

    def poll_many(self, scheduler_job_ids: Sequence[str]) -> dict[str, JobState]:
        # Use `kill -0 <pid>` which exits 0 if the process is alive, 1 otherwise.
        # Batch into a single shell to keep round-trip count to one.
        if not scheduler_job_ids:
            return {}
        checks = " ; ".join(
            f"kill -0 {_shell_quote(p)} 2>/dev/null && echo {_shell_quote(p)}=R || true"
            for p in scheduler_job_ids
        )
        try:
            result = self._transport.run(["bash", "-c", checks], timeout=15)
        except TransportError:
            return {}
        out: dict[str, JobState] = {}
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line.endswith("=R"):
                out[line[:-2]] = JobState.RUNNING
        return out

    def cancel(self, scheduler_job_id: str) -> None:
        # SIGTERM, brief grace period, SIGKILL — match LocalScheduler semantics.
        cmd = (
            f"kill -TERM {_shell_quote(scheduler_job_id)} 2>/dev/null ; "
            f"sleep 0.5 ; "
            f"kill -KILL {_shell_quote(scheduler_job_id)} 2>/dev/null ; true"
        )
        try:
            self._transport.run(["bash", "-c", cmd], timeout=10)
        except TransportError:
            pass

    def resolve_terminal(self, scheduler_job_id: str) -> TerminalStatus | None:
        # Without job_dir we can't read .exit_code; the reconciler must call
        # resolve_terminal_with_dir.  Mirror LocalScheduler.
        return None

    def list_queue(self, *, user: str | None = None) -> list[QueueEntry]:
        return []

    def format_dependency(self, edge: DependencyEdge) -> str:
        raise ConfigError(
            "scheduler 'local' does not support job dependencies",
            scheduler="local",
        )

    def format_dependencies(self, edges: Sequence[DependencyEdge]) -> str:
        raise ConfigError(
            "scheduler 'local' does not support job dependencies",
            scheduler="local",
        )

    def resolve_terminal_with_dir(
        self, scheduler_job_id: str, job_dir: Path
    ) -> TerminalStatus | None:
        exit_code_path = str(job_dir / ".exit_code")
        try:
            if not self._transport.exists(exit_code_path):
                return TerminalStatus(
                    state=JobState.LOST,
                    failure_reason="exit code file missing for shell job",
                )
            text = self._transport.read_text(exit_code_path).strip()
            code = int(text)
        except (FileNotFoundError, TransportError, ValueError):
            return TerminalStatus(
                state=JobState.LOST,
                failure_reason="exit code file unreadable for shell job",
            )
        state = JobState.SUCCEEDED if code == 0 else JobState.FAILED
        reason = None if code == 0 else f"process exited with code {code}"
        return TerminalStatus(state=state, exit_code=code, failure_reason=reason)

    def _materialize_script(self, spec: JobSpec, job_dir: Path) -> Path:
        script_path = job_dir / "run.sh"
        self._transport.write_text(
            str(script_path),
            _render_job_script(spec, job_dir),
            mode=0o700,
        )
        return script_path
