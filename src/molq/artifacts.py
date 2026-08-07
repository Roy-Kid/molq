"""Pulling a finished job's files back from the cluster.

Logs and working directories live on the *cluster's* filesystem. For a remote
destination these functions rsync over the transport; for a local one they are
a copy. Either way the destination is always local — this is the "bring it
home" direction.
"""

from __future__ import annotations

from pathlib import Path

from molq.models import JobRecord
from molq.transport import Transport

_STREAM_KEYS = {"stdout": "molq.stdout_path", "stderr": "molq.stderr_path"}


def local_scratch_dir(jobs_dir: Path | None, job_id: str, kind: str) -> Path:
    """Default local landing spot for fetched files.

    Falls back to ``./.molq/fetched`` rather than the job's own cwd, which for
    a remote cluster names a directory on the *other* machine.
    """
    base = jobs_dir or Path.cwd() / ".molq" / "fetched"
    return base / job_id / kind


def fetch_logs(
    transport: Transport,
    record: JobRecord,
    dest: Path,
    streams: tuple[str, ...] = ("stdout", "stderr"),
) -> dict[str, Path]:
    """Download the job's captured log files into *dest*.

    Returns ``stream -> local path`` for the streams that existed remotely;
    a stream that was never recorded or no longer exists is skipped rather
    than raising, since a job may legitimately produce only one of them.
    """
    dest.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for stream in streams:
        remote_path = record.metadata.get(_STREAM_KEYS[stream])
        if not remote_path or not transport.exists(remote_path):
            continue
        local_path = dest / f"{stream}.log"
        transport.download(remote_path, str(local_path))
        out[stream] = local_path
    return out


def fetch_job_dir(
    transport: Transport,
    record: JobRecord,
    dest: Path,
    exclude: tuple[str, ...] = (),
) -> Path:
    """Mirror the job's whole working directory into *dest*.

    Raises:
        FileNotFoundError: When the record carries no ``molq.job_dir``.
    """
    job_dir = record.metadata.get("molq.job_dir")
    if not job_dir:
        raise FileNotFoundError(
            f"Job {record.job_id} has no recorded molq.job_dir to mirror"
        )
    dest.mkdir(parents=True, exist_ok=True)
    transport.download(job_dir, str(dest), recursive=True, exclude=exclude)
    return dest
