"""Map molq JobRecord(s) → Nerve snapshot job dicts with rollup."""

from __future__ import annotations

import platform
import socket
import sys
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from molq.models import JobRecord
from molq.status import JobState

PRODUCER = {"id": "molq", "name": "molq", "kind": "queue.molq"}

_ATTENTION_STATES = frozenset({JobState.FAILED, JobState.TIMED_OUT, JobState.LOST})


def machine_alias() -> str:
    """Prefer macOS Bonjour LocalHostName (matches Nerve Settings)."""
    if sys.platform == "darwin":
        try:
            import subprocess

            out = subprocess.check_output(
                ["/usr/sbin/scutil", "--get", "LocalHostName"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1.0,
            ).strip()
            if out:
                return out
        except Exception:
            pass
    host = socket.gethostname() or "local"
    return host.split(".")[0].strip() or host


def machine_kind() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "darwin"
    if system == "linux":
        release = platform.release().lower()
        if "microsoft" in release or "wsl" in release:
            return "wsl"
        return "linux"
    if system == "windows":
        return "windows"
    return "unknown"


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts_iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _truncate(s: str | None, n: int = 160) -> str | None:
    if not s:
        return None
    s = " ".join(str(s).split())
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def _job_display_name(rec: JobRecord) -> str:
    meta_name = (rec.metadata or {}).get("job_name") or (rec.metadata or {}).get(
        "molq.job_name"
    )
    if meta_name:
        return str(meta_name)
    if rec.command_display:
        return _truncate(rec.command_display, 48) or rec.job_id[:8]
    return rec.job_id[:8]


def _group_key(rec: JobRecord) -> str:
    """Batch / chain grouping key for rollup.

    Prefer explicit metadata, then retry/root chain, else flat cluster bucket.
    """
    meta = rec.metadata or {}
    for key in ("molq.batch_id", "batch_id", "molq.chain_id", "chain_id"):
        if meta.get(key):
            return str(meta[key])
    if rec.retry_group_id:
        return f"retry:{rec.retry_group_id}"
    # root_job_id groups the whole chain (including the root row itself).
    if rec.root_job_id:
        return f"root:{rec.root_job_id}"
    return f"cluster:{rec.cluster_name}"


def facets_for_state(state: JobState) -> dict[str, Any]:
    """Structured Nerve facets from molq JobState (no free-text inference)."""
    if state in (JobState.CREATED, JobState.SUBMITTED):
        return {
            "lifecycle": "pending",
            "current": {"type": "submitted", "summary": state.value},
            "attention": {"level": "none"},
            "health": "ok",
            "progress": {"kind": "none"},
            "outcome": None,
        }
    if state == JobState.QUEUED:
        return {
            "lifecycle": "pending",
            "current": {"type": "queued", "summary": "queued"},
            "attention": {"level": "none", "reason": "queue"},
            "health": "ok",
            "progress": {"kind": "indeterminate", "label": "Queued"},
            "outcome": None,
        }
    if state == JobState.RUNNING:
        return {
            "lifecycle": "active",
            "current": {"type": "running", "summary": "running"},
            "attention": {"level": "none"},
            "health": "ok",
            "progress": {"kind": "indeterminate", "label": "Running"},
            "outcome": None,
        }
    if state == JobState.SUCCEEDED:
        return {
            "lifecycle": "ended",
            "current": {"type": "idle", "summary": "succeeded"},
            "attention": {"level": "none"},
            "health": "ok",
            "progress": {"kind": "none"},
            "outcome": "success",
        }
    if state == JobState.CANCELLED:
        return {
            "lifecycle": "ended",
            "current": {"type": "idle", "summary": "cancelled"},
            "attention": {"level": "none"},
            "health": "ok",
            "progress": {"kind": "none"},
            "outcome": "cancelled",
        }
    if state in (JobState.FAILED, JobState.TIMED_OUT, JobState.LOST):
        return {
            "lifecycle": "ended",
            "current": {"type": "idle", "summary": state.value},
            "attention": {
                "level": "suggested",
                "reason": "failure",
                "title": state.value,
                "summary": state.value,
            },
            "health": "degraded" if state != JobState.LOST else "unresponsive",
            "progress": {"kind": "none"},
            "outcome": "failure",
        }
    return {
        "lifecycle": "unknown",
        "current": {"type": "idle", "summary": state.value},
        "attention": {"level": "none"},
        "health": "unknown",
        "progress": {"kind": "none"},
        "outcome": None,
    }


def leaf_job_dict(
    rec: JobRecord,
    *,
    alias: str,
    version: int,
    paint_ribbon: bool,
    group_id: str | None,
    role: str = "member",
) -> dict[str, Any]:
    facets = facets_for_state(rec.state)
    summary_parts = [
        f"cluster={rec.cluster_name}",
        f"state={rec.state.value}",
    ]
    if rec.scheduler_job_id:
        summary_parts.append(f"sched={rec.scheduler_job_id}")
    if rec.failure_reason:
        summary_parts.append(_truncate(rec.failure_reason, 80) or "")
    facets["current"] = {
        **facets["current"],
        "name": _job_display_name(rec),
        "summary": _truncate(" · ".join(p for p in summary_parts if p), 160),
        "startedAt": _ts_iso(rec.started_at) or _ts_iso(rec.submitted_at),
    }
    job: dict[str, Any] = {
        "id": f"molq:{rec.job_id}",
        "kind": "job",
        "name": _job_display_name(rec),
        "alias": alias,
        "lifecycle": facets["lifecycle"],
        "current": facets["current"],
        "attention": facets["attention"],
        "health": facets["health"],
        "progress": facets["progress"],
        "producer": PRODUCER,
        "capabilities": [],
        "actions": [],
        "createdAt": _ts_iso(rec.submitted_at) or _now_iso(),
        "startedAt": _ts_iso(rec.started_at),
        "endedAt": _ts_iso(rec.finished_at),
        "updatedAt": _now_iso(),
        "version": version,
        "extensions": {
            "role": role,
            "paintRibbon": paint_ribbon,
            "molqJobId": rec.job_id,
            "cluster": rec.cluster_name,
            "scheduler": rec.scheduler,
        },
    }
    if facets["outcome"] is not None:
        job["outcome"] = facets["outcome"]
    if group_id:
        job["extensions"]["groupId"] = group_id
        job["extensions"]["parentJobId"] = (
            group_id  # legacy filter key; Nerve UI updated
        )
    return job


def _aggregate_facets(states: list[JobState]) -> dict[str, Any]:
    counts = Counter(s.value for s in states)
    n = len(states)
    n_term_ok = sum(1 for s in states if s == JobState.SUCCEEDED)
    n_fail = sum(1 for s in states if s in _ATTENTION_STATES)
    n_cancel = sum(1 for s in states if s == JobState.CANCELLED)
    n_run = sum(1 for s in states if s == JobState.RUNNING)
    n_queue = sum(
        1
        for s in states
        if s in (JobState.QUEUED, JobState.SUBMITTED, JobState.CREATED)
    )
    done = n_term_ok + n_fail + n_cancel
    ratio = (done / n) if n else 0.0

    metrics = [
        {"label": k, "current": float(v)}
        for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    if n_fail:
        lifecycle = "active" if (n_run or n_queue) else "ended"
        return {
            "lifecycle": lifecycle,
            "current": {
                "type": "batch",
                "summary": f"{n_fail} failed · {n_run} running · {n_queue} queued · {done}/{n}",
            },
            "attention": {
                "level": "suggested",
                "reason": "failure",
                "title": f"{n_fail} failed",
                "summary": f"{n_fail} of {n} jobs failed",
            },
            "health": "degraded",
            "progress": {
                "kind": "determinate",
                "ratio": ratio,
                "label": f"{done}/{n}",
                "metrics": metrics,
            },
            "outcome": "failure" if lifecycle == "ended" else None,
        }
    if n_run:
        return {
            "lifecycle": "active",
            "current": {
                "type": "batch",
                "summary": f"{n_run} running · {n_queue} queued · {done}/{n} done",
            },
            "attention": {"level": "none"},
            "health": "ok",
            "progress": {
                "kind": "determinate",
                "ratio": ratio,
                "label": f"{done}/{n}",
                "metrics": metrics,
            },
            "outcome": None,
        }
    if n_queue:
        return {
            "lifecycle": "pending",
            "current": {
                "type": "queued",
                "summary": f"{n_queue} queued · {done}/{n} done",
            },
            "attention": {"level": "none", "reason": "queue"},
            "health": "ok",
            "progress": {
                "kind": "determinate",
                "ratio": ratio,
                "label": f"{done}/{n}",
                "metrics": metrics,
            },
            "outcome": None,
        }
    # All terminal
    if n_fail == 0 and n_cancel == 0:
        outcome = "success"
    elif n_term_ok == 0 and n_fail == 0:
        outcome = "cancelled"
    elif n_fail:
        outcome = "failure"
    else:
        outcome = "partial"
    return {
        "lifecycle": "ended",
        "current": {"type": "idle", "summary": f"{n} jobs · {outcome}"},
        "attention": {"level": "none"},
        "health": "ok",
        "progress": {
            "kind": "determinate",
            "ratio": 1.0,
            "label": f"{n}/{n}",
            "metrics": metrics,
        },
        "outcome": outcome,
    }


def _chain_stage_info(records: list[JobRecord]) -> dict[str, Any]:
    """Ordered stage list + human summary for dependency/retry chains."""
    ordered = sorted(
        records,
        key=lambda r: (
            r.attempt,
            r.submitted_at if r.submitted_at is not None else 0.0,
            r.job_id,
        ),
    )
    stages: list[dict[str, Any]] = []
    for i, rec in enumerate(ordered, start=1):
        stages.append(
            {
                "index": i,
                "jobId": rec.job_id,
                "name": _job_display_name(rec),
                "state": rec.state.value,
            }
        )
    # Current stage: first non-terminal; else last
    current_idx = len(stages)
    for st in stages:
        if st["state"] not in {s.value for s in JobState if s.is_terminal}:
            current_idx = int(st["index"])
            break
    current = stages[current_idx - 1] if stages else None
    if current is None:
        summary = "empty chain"
    else:
        summary = f"stage {current_idx}/{len(stages)} · {current['name']} · {current['state']}"
    return {
        "stages": stages,
        "currentIndex": current_idx,
        "stageCount": len(stages),
        "summary": summary,
    }


def group_job_dict(
    *,
    group_id: str,
    name: str,
    records: list[JobRecord],
    alias: str,
    version: int,
    kind: str = "batch",
    force_end: bool = False,
) -> dict[str, Any]:
    states = [r.state for r in records]
    facets = _aggregate_facets(states)
    chain_info: dict[str, Any] | None = None
    if kind == "chain":
        chain_info = _chain_stage_info(records)
        # Prefer stage line for activity column; keep counts in progress.
        facets = {
            **facets,
            "current": {
                "type": "pipeline",
                "name": name,
                "summary": chain_info["summary"],
            },
        }
    if force_end and facets["lifecycle"] != "ended":
        facets = {
            **facets,
            "lifecycle": "ended",
            "outcome": facets.get("outcome") or "cancelled",
            "current": {"type": "idle", "summary": "detached"},
        }
    counts = {s.value: c for s, c in Counter(states).items()}
    submitted = [r.submitted_at for r in records if r.submitted_at is not None]
    started = [r.started_at for r in records if r.started_at is not None]
    finished = [r.finished_at for r in records if r.finished_at is not None]
    extensions: dict[str, Any] = {
        "role": "group",
        "paintRibbon": True,
        "memberCount": len(records),
        "counts": {k: int(v) for k, v in counts.items()},
    }
    if chain_info is not None:
        extensions["stages"] = chain_info["stages"]
        extensions["currentStage"] = chain_info["currentIndex"]
        extensions["stageCount"] = chain_info["stageCount"]
    job: dict[str, Any] = {
        "id": group_id,
        "kind": kind,
        "name": name,
        "alias": alias,
        "lifecycle": facets["lifecycle"],
        "current": facets["current"],
        "attention": facets["attention"],
        "health": facets["health"],
        "progress": facets["progress"],
        "producer": PRODUCER,
        "capabilities": [],
        "actions": [],  # display-only producer — no reverse control
        "createdAt": _ts_iso(min(submitted)) if submitted else _now_iso(),
        "startedAt": _ts_iso(min(started)) if started else None,
        "endedAt": (
            _ts_iso(max(finished))
            if finished and facets["lifecycle"] == "ended"
            else None
        ),
        "updatedAt": _now_iso(),
        "version": version,
        "extensions": extensions,
    }
    if facets.get("outcome") is not None:
        job["outcome"] = facets["outcome"]
    return job


# Type aliases for callers
GroupSnapshot = dict[str, Any]
LeafSnapshot = dict[str, Any]


def build_snapshots(
    *,
    records: list[JobRecord],
    cluster_name: str,
    expand_threshold: int,
    show_members: str,
    version: int,
    force_end: bool,
    alias: str,
) -> list[dict[str, Any]]:
    """Build Nerve job snapshots with rollup for high cardinality."""
    if not records:
        if force_end:
            # Nothing to end.
            return []
        return []

    # Bucket by group key
    buckets: dict[str, list[JobRecord]] = {}
    for rec in records:
        buckets.setdefault(_group_key(rec), []).append(rec)

    out: list[dict[str, Any]] = []
    total = len(records)

    # Flatten mode: few jobs overall → individual ribbon roots
    if total <= expand_threshold and len(buckets) == 1:
        only = next(iter(buckets.values()))
        # Single small group without explicit multi-batch: leaves as roots
        for rec in only:
            out.append(
                leaf_job_dict(
                    rec,
                    alias=alias,
                    version=version,
                    paint_ribbon=True,
                    group_id=None,
                    role="job",
                )
            )
        return out

    for gkey, members in buckets.items():
        group_id = f"molq:{cluster_name}:{gkey}"
        # Human name
        if gkey.startswith("cluster:"):
            name = f"molq · {cluster_name}"
            kind = "queue"
        elif gkey.startswith("retry:"):
            name = f"retry · {gkey.split(':', 1)[-1][:8]}"
            kind = "chain"
        elif gkey.startswith("root:"):
            name = f"chain · {gkey.split(':', 1)[-1][:8]}"
            kind = "chain"
        else:
            name = f"batch · {gkey[:24]}"
            kind = "batch"

        out.append(
            group_job_dict(
                group_id=group_id,
                name=name,
                records=members,
                alias=alias,
                version=version,
                kind=kind,
                force_end=force_end,
            )
        )

        # Member leaves for panel tree (paintRibbon=false).
        # Chains always include every stage so the tree can show the pipeline.
        # Batches respect show_members (never | attention | all).
        for rec in members:
            include = False
            if kind == "chain" or show_members == "all":
                include = True
            elif show_members == "attention":
                include = rec.state in _ATTENTION_STATES
            # never → no members (except chain, handled above)
            if not include:
                continue
            leaf = leaf_job_dict(
                rec,
                alias=alias,
                version=version,
                paint_ribbon=False,
                group_id=group_id,
                role="member",
            )
            if kind == "chain":
                # Stage index for panel detail
                ordered_ids = [
                    r.job_id
                    for r in sorted(
                        members,
                        key=lambda r: (
                            r.attempt,
                            r.submitted_at if r.submitted_at is not None else 0.0,
                            r.job_id,
                        ),
                    )
                ]
                try:
                    stage_i = ordered_ids.index(rec.job_id) + 1
                except ValueError:
                    stage_i = 0
                leaf["extensions"]["stageIndex"] = stage_i
                leaf["extensions"]["stageCount"] = len(ordered_ids)
                leaf["current"] = {
                    **leaf.get("current", {}),
                    "summary": _truncate(
                        f"stage {stage_i}/{len(ordered_ids)} · "
                        f"{leaf.get('current', {}).get('summary', rec.state.value)}",
                        160,
                    ),
                }
            out.append(leaf)

    return out
