"""Applying a retention policy: expiring job directories and old records.

Two independent clocks. Job *directories* usually expire first — they are the
bulk on disk — while the database rows stay queryable for longer, so
``molq history`` can still show what ran after the scratch files are gone.
"""

from __future__ import annotations

import shutil
import time

from molq.models import RetentionPolicy
from molq.store import JobStore

_SECONDS_PER_DAY = 86400


def apply_retention(
    store: JobStore,
    cluster_name: str,
    policy: RetentionPolicy,
    *,
    now: float | None = None,
    dry_run: bool = False,
) -> dict[str, list[str]]:
    """Delete what the policy says has expired for *cluster_name*.

    Args:
        store: Where records live.
        cluster_name: Only this cluster's jobs are considered.
        policy: Age thresholds and whether failed job dirs are spared.
        now: Reference time; defaults to the wall clock. Injectable for tests.
        dry_run: Report what would go without removing anything.

    Returns:
        ``{"job_dirs": [...], "records": [...]}`` — what was deleted, or what
        would have been under *dry_run*.
    """
    timestamp = time.time() if now is None else now
    artifact_candidates, record_candidates = store.list_cleanup_candidates(
        cluster_name,
        job_dir_cutoff=timestamp - policy.keep_job_dirs_for_days * _SECONDS_PER_DAY,
        record_cutoff=(
            timestamp - policy.keep_terminal_records_for_days * _SECONDS_PER_DAY
        ),
        include_failed_job_dirs=not policy.keep_failed_job_dirs,
    )

    deleted_dirs: list[str] = []
    for record in artifact_candidates:
        job_dir = record.metadata.get("molq.job_dir")
        if not job_dir:
            continue
        deleted_dirs.append(job_dir)
        if not dry_run:
            # ignore_errors: a directory already removed by hand, or living on
            # a filesystem that is currently unmounted, must not abort the
            # rest of the sweep.
            shutil.rmtree(job_dir, ignore_errors=True)
            store.update_job(record.job_id, cleaned_at=timestamp)

    deleted_records = [record.job_id for record in record_candidates]
    if deleted_records and not dry_run:
        store.delete_terminal_records(deleted_records)

    return {"job_dirs": deleted_dirs, "records": deleted_records}
