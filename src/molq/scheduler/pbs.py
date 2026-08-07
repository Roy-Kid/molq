"""PBS / Torque backend (qsub / qstat / qdel / tracejob)."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

import mollog

from molq.errors import SchedulerError
from molq.models import JobSpec
from molq.options import PBSSchedulerOptions
from molq.scheduler.base import (
    DependencyEdge,
    QueueEntry,
    SchedulerCapabilities,
    TerminalStatus,
    _dependency_keyword,
)
from molq.scheduler.script import _render_job_lines
from molq.status import JobState
from molq.transport import LocalTransport, Transport, TransportError

logger = mollog.get_logger(__name__)

_PBS_STATE_MAP: dict[str, JobState] = {
    "R": JobState.RUNNING,
    "Q": JobState.QUEUED,
    "H": JobState.QUEUED,
    "E": JobState.RUNNING,
    "C": JobState.SUCCEEDED,
    "T": JobState.RUNNING,
    "W": JobState.QUEUED,
    "S": JobState.QUEUED,
}


class PBSScheduler:
    """Submit and manage jobs via PBS/Torque.

    All shell calls (``qsub``, ``qstat``, ``qdel``, ``tracejob``) go through
    the injected :class:`~molq.transport.Transport`.
    """

    def __init__(
        self,
        options: PBSSchedulerOptions | None = None,
        *,
        transport: Transport | None = None,
    ) -> None:
        self._opts = options or PBSSchedulerOptions()
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
            supports_time_limit=True,
            supports_partition=True,
            supports_account=True,
            supports_node_count=True,
            supports_dependency=True,
        )

    def submit(self, spec: JobSpec, job_dir: Path) -> str:
        script_path = self._generate_script(spec, job_dir)
        cmd = [self._opts.qsub_path, str(script_path)]
        cmd.extend(self._opts.extra_qsub_flags)

        try:
            result = self._transport.run(cmd, timeout=60)
        except TransportError as e:
            raise SchedulerError("PBS submission timed out", command=cmd) from e
        if result.returncode != 0:
            raise SchedulerError(
                "PBS submission failed",
                stderr=result.stderr,
                command=cmd,
            )
        return result.stdout.strip().split(".")[0]

    def poll_many(self, scheduler_job_ids: Sequence[str]) -> dict[str, JobState]:
        if not scheduler_job_ids:
            return {}

        # Query specific job IDs directly — O(queried) not O(all user jobs).
        # qstat exits non-zero for unknown/finished jobs; that's fine — those
        # jobs will be resolved as terminal by the reconciler.
        cmd = [self._opts.qstat_path] + list(scheduler_job_ids)

        try:
            result = self._transport.run(cmd, timeout=30)
        except TransportError as e:
            logger.warning(f"qstat invocation failed: {e}")
            return {}
        if not result.stdout.strip():
            return {}

        wanted = set(scheduler_job_ids)
        out: dict[str, JobState] = {}
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("-") or line.startswith("Job"):
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            jid = parts[0].split(".")[0]
            if jid in wanted:
                st = parts[4]
                state = _PBS_STATE_MAP.get(st)
                if state is not None:
                    out[jid] = state
        return out

    def cancel(self, scheduler_job_id: str) -> None:
        try:
            self._transport.run(
                [self._opts.qdel_path, scheduler_job_id],
                timeout=30,
            )
        except TransportError:
            pass

    def resolve_terminal(self, scheduler_job_id: str) -> TerminalStatus | None:
        try:
            result = self._transport.run(
                [self._opts.tracejob_path, scheduler_job_id],
                timeout=15,
            )
        except TransportError:
            return None
        if result.returncode != 0 or not result.stdout.strip():
            return None
        for line in result.stdout.split("\n"):
            if "Exit_status=" in line:
                try:
                    code = line.split("Exit_status=")[1].split()[0]
                    exit_code = int(code)
                except (IndexError, ValueError):
                    return None
                if exit_code == 0:
                    return TerminalStatus(state=JobState.SUCCEEDED, exit_code=0)
                if exit_code < 0:
                    return TerminalStatus(
                        state=JobState.CANCELLED,
                        exit_code=exit_code,
                        failure_reason=f"PBS job cancelled (exit {exit_code})",
                    )
                return TerminalStatus(
                    state=JobState.FAILED,
                    exit_code=exit_code,
                    failure_reason=f"PBS job failed with exit code {exit_code}",
                )
        return None

    def list_queue(self, *, user: str | None = None) -> list[QueueEntry]:
        target_user = user or os.environ.get("USER") or ""
        cmd: list[str] = [self._opts.qstat_path]
        if target_user:
            cmd += ["-u", target_user]
        try:
            result = self._transport.run(cmd, timeout=30)
        except TransportError as exc:
            logger.warning(f"qstat invocation failed: {exc}")
            return []
        if result.returncode != 0 or not result.stdout.strip():
            return []
        entries: list[QueueEntry] = []
        for line in result.stdout.split("\n"):
            line = line.strip()
            if not line or line.startswith("-") or line.startswith("Job"):
                continue
            parts = line.split()
            # Typical columns: id user queue jobname sessid nds tsk req_mem req_time s elap
            if len(parts) < 10:
                continue
            jid = parts[0].split(".")[0]
            usr = parts[1]
            partition = parts[2]
            name = parts[3]
            raw_state = parts[9] if len(parts) > 9 else ""
            entries.append(
                QueueEntry(
                    scheduler_job_id=jid,
                    name=name or None,
                    user=usr or None,
                    state=_PBS_STATE_MAP.get(raw_state, JobState.QUEUED),
                    raw_state=raw_state,
                    partition=partition or None,
                )
            )
        return entries

    # -W depend=<type>:<jobid>[:<jobid2>...][,<type2>:<jobid3>...]
    _DEP_KEYWORDS: dict[str, str] = {
        "after_started": "after",
        "after_success": "afterok",
        "after_failure": "afternotok",
        "after": "afterany",
    }

    def format_dependency(self, edge: DependencyEdge) -> str:
        keyword = _dependency_keyword(self._DEP_KEYWORDS, edge.condition, "pbs")
        return f"{keyword}:{edge.scheduler_job_id}"

    def format_dependencies(self, edges: Sequence[DependencyEdge]) -> str:
        # PBS colon-joins ids sharing a type, then comma-joins the groups:
        # afterok:123:456,afternotok:789
        groups: dict[str, list[str]] = {}
        for edge in edges:
            keyword = _dependency_keyword(self._DEP_KEYWORDS, edge.condition, "pbs")
            groups.setdefault(keyword, []).append(edge.scheduler_job_id)
        return ",".join(f"{keyword}:{':'.join(ids)}" for keyword, ids in groups.items())

    def _generate_script(self, spec: JobSpec, job_dir: Path) -> Path:
        script_path = job_dir / "run_pbs.sh"
        lines = ["#!/bin/bash"]

        directives = self._map_resources(spec)
        for key, value in directives.items():
            if key == "-l":
                for item in value.split(","):
                    lines.append(f"#PBS -l {item}")
            else:
                lines.append(f"#PBS {key} {value}")

        lines.extend(_render_job_lines(spec, job_dir))

        self._transport.write_text(
            str(script_path), "\n".join(lines) + "\n", mode=0o700
        )
        return script_path

    def _map_resources(self, spec: JobSpec) -> dict[str, str]:
        mapped: dict[str, str] = {}
        r, s, e = spec.resources, spec.scheduling, spec.execution

        resource_parts: list[str] = []
        node_count = s.node_count or 1
        ppn = r.cpu_count if s.node_count is None else None
        if ppn:
            resource_parts.append(f"nodes={node_count}:ppn={ppn}")
        else:
            resource_parts.append(f"nodes={node_count}")

        if r.memory:
            resource_parts.append(f"mem={r.memory.to_pbs()}")
        if r.time_limit:
            resource_parts.append(f"walltime={r.time_limit.to_pbs()}")
        if r.gpu_count:
            resource_parts.append(f"gpus={r.gpu_count}")

        mapped["-l"] = ",".join(resource_parts)

        if e.job_name:
            mapped["-N"] = e.job_name
        if e.output_file:
            mapped["-o"] = e.output_file
        if e.error_file:
            mapped["-e"] = e.error_file
        if s.partition:
            mapped["-q"] = s.partition
        if s.account:
            mapped["-A"] = s.account
        if s.dependency:
            mapped["-W"] = f"depend={s.dependency}"

        return mapped
