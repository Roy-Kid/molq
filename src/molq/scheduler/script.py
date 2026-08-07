"""Job-script rendering and scheduler-output parsing shared by all backends."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from molq.models import JobSpec
from molq.status import JobState


def _shell_quote(s: str) -> str:
    """Quote a string for safe shell usage."""
    if not s:
        return "''"
    if re.match(r"^[a-zA-Z0-9_/.\-=:@]+$", s):
        return s
    return "'" + s.replace("'", "'\"'\"'") + "'"


def _render_job_script(spec: JobSpec, job_dir: Path) -> str:
    return "\n".join(["#!/bin/bash", *_render_job_lines(spec, job_dir)]) + "\n"


def _render_job_lines(spec: JobSpec, job_dir: Path) -> list[str]:
    lines: list[str] = [""]

    if spec.execution.cwd:
        lines.append(f"cd {_shell_quote(str(spec.execution.cwd))}")

    if spec.execution.env:
        for key, value in sorted(spec.execution.env.items()):
            lines.append(f"export {key}={_shell_quote(value)}")

    payload = _payload_lines(spec, job_dir)
    if payload:
        lines.extend(payload)
    return lines


def _payload_lines(spec: JobSpec, job_dir: Path) -> list[str]:
    cmd = spec.command
    if cmd.argv is not None:
        return [" ".join(_shell_quote(a) for a in cmd.argv)]
    if cmd.command is not None:
        return [cmd.command]
    if cmd.script is not None:
        if cmd.script.variant == "inline":
            return list((cmd.script.text or "").splitlines())
        if cmd.script.variant == "path":
            # Single-quote rather than interpolate: a job_dir containing a
            # space, quote, or `$` would otherwise break the generated script
            # or splice shell expansion into it.
            return [f"bash {_shell_quote(str(job_dir / 'user_script.sh'))}"]
    return []


def _parse_exit_code(field: str) -> int | None:
    try:
        return int(field.split(":")[0])
    except (ValueError, IndexError):
        return None


_SLURM_TIME_FORMATS: tuple[str, ...] = ("%Y-%m-%dT%H:%M:%S",)
_LSF_TIME_FORMATS: tuple[str, ...] = (
    "%Y-%m-%dT%H:%M:%S",
    "%b %d %H:%M %Y",
    "%b %d %H:%M",
)
_QUEUE_TIME_SENTINELS = frozenset({"", "-", "N/A", "Unknown"})


def _parse_queue_time(field: str, formats: tuple[str, ...]) -> float | None:
    """Parse a scheduler timestamp; return None for sentinel values.

    Year-less LSF timestamps are anchored to the current year so they match
    the scheduler client's display behavior.
    """
    field = field.strip()
    if field in _QUEUE_TIME_SENTINELS:
        return None
    for fmt in formats:
        try:
            ts = datetime.strptime(field, fmt)
        except ValueError:
            continue
        if ts.year == 1900:
            ts = ts.replace(year=datetime.now().year)
        return ts.timestamp()
    return None


def _parse_slurm_time(field: str) -> float | None:
    return _parse_queue_time(field, _SLURM_TIME_FORMATS)


def _parse_lsf_time(field: str) -> float | None:
    return _parse_queue_time(field, _LSF_TIME_FORMATS)


def _default_failure_reason(
    state: JobState, exit_code: int | None, raw_state: str | None = None
) -> str | None:
    if state == JobState.SUCCEEDED:
        return None
    if state == JobState.CANCELLED:
        return f"job was cancelled ({raw_state})" if raw_state else "job was cancelled"
    if state == JobState.TIMED_OUT:
        return "job exceeded its time limit"
    if state == JobState.LOST:
        return "job disappeared from scheduler"
    if exit_code is not None:
        return f"job failed with exit code {exit_code}"
    if raw_state:
        return f"job failed with scheduler state {raw_state}"
    return "job failed"
