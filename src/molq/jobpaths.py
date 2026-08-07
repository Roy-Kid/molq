"""Where a job's scripts, logs, and artifacts live.

All paths here are interpreted on the *cluster's* filesystem — the same string
means different machines for a local and an SSH transport — so nothing in this
module touches the local disk. Directory creation goes through a
:class:`~molq.transport.Transport`.
"""

from __future__ import annotations

import json
from pathlib import Path

from molq.models import JobSpec
from molq.transport import Transport
from molq.types import Script


def default_jobs_dir(cwd: str) -> Path:
    """Per-submission fallback root: ``<cwd>/.molq/jobs``."""
    return Path(cwd) / ".molq" / "jobs"


def job_dir_root(jobs_dir: Path | None, cwd: str) -> Path:
    """The configured jobs root, or the per-submission default under *cwd*."""
    return jobs_dir or default_jobs_dir(cwd)


def job_dir_path(
    jobs_dir: Path | None,
    job_id: str,
    cwd: str,
    dir_name: str | None = None,
) -> Path:
    """Directory for one job — *dir_name* when given, else the job id."""
    return job_dir_root(jobs_dir, cwd) / (dir_name or job_id)


def prepare_job_dir(
    transport: Transport,
    jobs_dir: Path | None,
    job_id: str,
    cwd: str,
    dir_name: str | None = None,
) -> Path:
    """Create the job directory on the transport's filesystem and lock it down."""
    transport.mkdir(str(job_dir_root(jobs_dir, cwd)), parents=True, exist_ok=True)
    job_dir = job_dir_path(jobs_dir, job_id, cwd, dir_name)
    transport.mkdir(str(job_dir), parents=True, exist_ok=True)
    # mode=0o700 is honoured by LocalTransport-backed pathlib only on
    # creation; for SshTransport mkdir uses the remote umask.  Set it
    # explicitly so both paths converge.
    try:
        transport.chmod(str(job_dir), 0o700)
    except Exception:
        # chmod failures are non-fatal — the directory exists and is usable.
        pass
    return job_dir


def resolve_cwd(cwd: str | Path | None) -> str:
    """Absolute working directory for a submission; defaults to the process cwd."""
    base = Path(cwd).expanduser() if cwd is not None else Path.cwd()
    return str(base.resolve())


def resolve_output_path(
    path: str | None,
    cwd: str,
    job_dir: Path,
    default_name: str,
) -> Path:
    """Absolute path for a log stream.

    ``None`` lands in the job directory under *default_name*; a relative path
    is taken against the job's working directory, not the driver's.
    """
    if path is None:
        return job_dir / default_name
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return Path(cwd) / candidate


def materialize_script(transport: Transport, script: Script, job_dir: Path) -> None:
    """Stage a ``Script.path(...)`` into the job directory.

    Reads the user's file from the *local* filesystem and writes it through
    the transport, so for an SSH destination the copy lands on the remote
    host. Inline scripts need no staging — the backend renders them into the
    generated job script.
    """
    if script.variant != "path" or not script.file_path:
        return
    content = Path(script.file_path).read_bytes()
    transport.write_bytes(str(job_dir / "user_script.sh"), content, mode=0o700)


def write_manifest(
    transport: Transport,
    jobs_dir: Path | None,
    spec: JobSpec,
    now: float,
) -> None:
    """Drop a ``manifest.json`` beside the job so its files are self-describing.

    Anyone landing in a job directory — a human over ssh, a cleanup script —
    can tell which molq job it belongs to and where its streams went, without
    the database.
    """
    job_dir = job_dir_path(jobs_dir, spec.job_id, spec.cwd, spec.dir_name)
    has_script_file = (
        spec.command.script is not None and spec.command.script.variant == "path"
    )
    transport.write_text(
        str(job_dir / "manifest.json"),
        json.dumps(
            {
                "job_id": spec.job_id,
                "root_job_id": spec.root_job_id,
                "attempt": spec.attempt,
                "script_path": str(job_dir / "user_script.sh")
                if has_script_file
                else None,
                "stdout_path": spec.metadata.get("molq.stdout_path"),
                "stderr_path": spec.metadata.get("molq.stderr_path"),
                "created_at": now,
            },
            sort_keys=True,
        ),
        mode=0o600,
    )
