"""IBM Spectrum LSF backend (bsub / bjobs / bkill / bhist)."""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from pathlib import Path

import mollog

from molq.errors import SchedulerError
from molq.models import JobSpec
from molq.options import LSFSchedulerOptions
from molq.scheduler.base import (
    DependencyEdge,
    QueueEntry,
    SchedulerCapabilities,
    TerminalStatus,
    _dependency_keyword,
)
from molq.scheduler.script import (
    _default_failure_reason,
    _parse_lsf_time,
    _render_job_lines,
)
from molq.status import JobState
from molq.transport import LocalTransport, Transport, TransportError

logger = mollog.get_logger(__name__)

# Phrases `bhist -l` emits for a finished job.  Anchored to LSF's own wording
# so the job's echoed command line cannot be mistaken for an outcome.
_LSF_DONE_RE = re.compile(r"done successfully|completed\s*<done>")
_LSF_EXIT_CODE_RE = re.compile(r"exited with exit code\s+(\d+)")
_LSF_EXITED_RE = re.compile(r"\bexited\b|completed\s*<exit>")
_LSF_KILLED_RE = re.compile(r"term_owner|term_force_owner|signal\s*<kill>")

_LSF_STATE_MAP: dict[str, JobState] = {
    "RUN": JobState.RUNNING,
    "PEND": JobState.QUEUED,
    "DONE": JobState.SUCCEEDED,
    "EXIT": JobState.FAILED,
    "USUSP": JobState.QUEUED,
    "SSUSP": JobState.QUEUED,
    "PSUSP": JobState.QUEUED,
    "WAIT": JobState.QUEUED,
    "ZOMBI": JobState.FAILED,
}


class LSFScheduler:
    """Submit and manage jobs via IBM Spectrum LSF.

    All shell calls (``bsub``, ``bjobs``, ``bkill``, ``bhist``) go through the
    injected :class:`~molq.transport.Transport`.
    """

    def __init__(
        self,
        options: LSFSchedulerOptions | None = None,
        *,
        transport: Transport | None = None,
    ) -> None:
        self._opts = options or LSFSchedulerOptions()
        self._transport: Transport = transport or LocalTransport()

    def capabilities(self) -> SchedulerCapabilities:
        return SchedulerCapabilities(
            supports_cwd=True,
            supports_env=True,
            supports_output_file=True,
            supports_error_file=True,
            supports_job_name=True,
            supports_cpu_count=True,
            supports_memory=True,
            supports_gpu_count=True,
            supports_gpu_type=True,
            supports_time_limit=True,
            supports_partition=True,
            supports_account=True,
            supports_dependency=True,
        )

    def submit(self, spec: JobSpec, job_dir: Path) -> str:
        script_path = self._generate_script(spec, job_dir)
        cmd = [self._opts.bsub_path]
        cmd.extend(self._opts.extra_bsub_flags)

        # bsub reads the job script from stdin.  Read it back via the same
        # transport we just wrote it through so SSH-routed schedulers don't
        # try to read a remote-only file from the local filesystem.
        script_content = self._transport.read_text(str(script_path))
        try:
            result = self._transport.run(cmd, input=script_content, timeout=60)
        except TransportError as e:
            raise SchedulerError("LSF submission timed out", command=cmd) from e
        if result.returncode != 0:
            raise SchedulerError(
                "LSF submission failed",
                stderr=result.stderr,
                command=cmd,
            )
        match = re.search(r"Job <(\d+)>", result.stdout)
        if not match:
            raise SchedulerError(
                f"Could not parse job ID from bsub output: {result.stdout}",
                command=cmd,
            )
        return match.group(1)

    def poll_many(self, scheduler_job_ids: Sequence[str]) -> dict[str, JobState]:
        if not scheduler_job_ids:
            return {}

        cmd = [self._opts.bjobs_path, "-noheader"] + list(scheduler_job_ids)

        try:
            result = self._transport.run(cmd, timeout=30)
        except TransportError as e:
            logger.warning(f"bjobs invocation failed: {e}")
            return {}
        if not result.stdout.strip():
            return {}

        wanted = set(scheduler_job_ids)
        out: dict[str, JobState] = {}
        for line in result.stdout.strip().split("\n"):
            parts = line.split()
            if len(parts) < 3:
                continue
            jid = parts[0]
            if jid in wanted:
                st = parts[2]
                state = _LSF_STATE_MAP.get(st)
                if state is not None:
                    out[jid] = state
        return out

    def cancel(self, scheduler_job_id: str) -> None:
        try:
            self._transport.run(
                [self._opts.bkill_path, scheduler_job_id],
                timeout=30,
            )
        except TransportError:
            pass

    def resolve_terminal(self, scheduler_job_id: str) -> TerminalStatus | None:
        try:
            result = self._transport.run(
                [self._opts.bhist_path, "-l", scheduler_job_id],
                timeout=15,
            )
        except TransportError:
            return None
        if result.returncode != 0 or not result.stdout.strip():
            return None

        lower = result.stdout.lower()

        # `bhist -l` is prose, and it echoes the job's own command line back.
        # Match the phrases LSF actually emits rather than bare substrings —
        # a job named "rundone" or a path containing "exit" used to decide the
        # outcome.
        if _LSF_KILLED_RE.search(lower):
            return TerminalStatus(
                state=JobState.CANCELLED,
                failure_reason=_default_failure_reason(
                    JobState.CANCELLED, None, "killed"
                ),
                raw_state="killed",
            )
        if _LSF_DONE_RE.search(lower):
            return TerminalStatus(
                state=JobState.SUCCEEDED, exit_code=0, raw_state="done"
            )
        match = _LSF_EXIT_CODE_RE.search(lower)
        if match is not None or _LSF_EXITED_RE.search(lower):
            code = int(match.group(1)) if match is not None else None
            return TerminalStatus(
                state=JobState.FAILED,
                exit_code=code,
                failure_reason=_default_failure_reason(JobState.FAILED, code, "exit"),
                raw_state="exit",
            )
        return None

    def list_queue(self, *, user: str | None = None) -> list[QueueEntry]:
        target_user = user or os.environ.get("USER") or ""
        cmd: list[str] = [
            self._opts.bjobs_path,
            "-noheader",
            "-o",
            "jobid stat job_name user queue submit_time start_time",
        ]
        if target_user:
            cmd += ["-u", target_user]
        try:
            result = self._transport.run(cmd, timeout=30)
        except TransportError as exc:
            logger.warning(f"bjobs invocation failed: {exc}")
            return []
        if result.returncode != 0 or not result.stdout.strip():
            return []
        entries: list[QueueEntry] = []
        for line in result.stdout.strip().split("\n"):
            parts = line.split()
            if len(parts) < 5:
                continue
            jid = parts[0]
            raw_state = parts[1]
            name = parts[2]
            usr = parts[3]
            partition = parts[4]
            sub_t = " ".join(parts[5:8]) if len(parts) >= 8 else ""
            start_t = " ".join(parts[8:11]) if len(parts) >= 11 else ""
            entries.append(
                QueueEntry(
                    scheduler_job_id=jid,
                    name=None if name in ("-", "") else name,
                    user=usr or None,
                    state=_LSF_STATE_MAP.get(raw_state, JobState.QUEUED),
                    raw_state=raw_state,
                    partition=partition or None,
                    submit_time=_parse_lsf_time(sub_t),
                    start_time=_parse_lsf_time(start_t),
                )
            )
        return entries

    # -w "<expr> [&& <expr2> ...]"
    _DEP_KEYWORDS: dict[str, str] = {
        "after_started": "started",
        "after_success": "done",
        "after_failure": "exit",
        "after": "ended",
    }

    def format_dependency(self, edge: DependencyEdge) -> str:
        keyword = _dependency_keyword(self._DEP_KEYWORDS, edge.condition, "lsf")
        return f"{keyword}({edge.scheduler_job_id})"

    def format_dependencies(self, edges: Sequence[DependencyEdge]) -> str:
        return " && ".join(self.format_dependency(edge) for edge in edges)

    def _generate_script(self, spec: JobSpec, job_dir: Path) -> Path:
        script_path = job_dir / "run_lsf.sh"
        lines = ["#!/bin/bash"]

        directives = self._map_resources(spec)
        for key, value in directives.items():
            lines.append(f"#BSUB {key} {value}")

        lines.extend(_render_job_lines(spec, job_dir))

        self._transport.write_text(
            str(script_path), "\n".join(lines) + "\n", mode=0o700
        )
        return script_path

    def _map_resources(self, spec: JobSpec) -> dict[str, str]:
        mapped: dict[str, str] = {}
        r, s, e = spec.resources, spec.scheduling, spec.execution

        if s.partition:
            mapped["-q"] = s.partition
        if r.cpu_count:
            mapped["-n"] = str(r.cpu_count)
        if r.memory:
            mapped["-M"] = str(r.memory.to_lsf_kb())
        if r.time_limit:
            mapped["-W"] = str(r.time_limit.to_lsf_minutes())
        if e.job_name:
            name = e.job_name
            if s.array_spec:
                name = f"{name}[{s.array_spec}]"
            mapped["-J"] = name
        if e.output_file:
            mapped["-o"] = e.output_file
        if e.error_file:
            mapped["-e"] = e.error_file
        if s.account:
            mapped["-P"] = s.account
        if r.gpu_count:
            gpu_str = f"num={r.gpu_count}"
            if r.gpu_type:
                gpu_str += f":mode=exclusive_process:gmodel={r.gpu_type}"
            mapped["-gpu"] = gpu_str
        if s.dependency:
            mapped["-w"] = f'"{s.dependency}"'

        return mapped
