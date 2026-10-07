"""Disposable runtime snapshots, scoped baselines, event ring and freshness."""

from __future__ import annotations

import copy
import json
import time
import uuid
from collections import OrderedDict, deque
from datetime import UTC, datetime
from typing import Any

from molq.scheduler.base import TERMINAL, NativeJob


def now() -> str:
    """Return an RFC3339 observation time, not native transition time."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def key(ref: dict) -> str:
    """Keep registry, Cluster, native ID and incarnation in every cache key."""
    return "|".join(
        ref[k] for k in ("registry_id", "cluster_id", "native_id", "incarnation")
    )


def snapshot(
    ref: dict, job: NativeJob | None, *, error: dict | None = None
) -> dict[str, Any]:
    """Compose canonical observations; unavailable is never terminal."""
    state = job.state if job else "unknown"
    result = {
        "ref": ref,
        "state": state,
        "terminal": state in TERMINAL,
        "observed_at": now(),
        "freshness": {"status": "live", "age_seconds": 0},
        "source": job.source if job else "unavailable" if error else "absent",
        "raw_state": job.raw_state if job else "",
        "exit_code": job.exit_code if job else None,
    }
    if error:
        result["error"] = error
        result["freshness"]["status"] = "unavailable"
        result["terminal"] = False
    return result


def collection(snapshots: list[dict], errors: list[dict] | None = None) -> dict:
    """Compute shared completion once, including absence/partial coverage."""
    errors = errors or []
    complete = not errors and all(
        s["source"] not in {"absent", "unavailable"} for s in snapshots
    )
    terminal = complete and bool(snapshots) and all(s["terminal"] for s in snapshots)
    return {
        "snapshots": snapshots,
        "coverage": {"complete": complete, "errors": errors},
        "completion": {
            "all_confirmed_terminal": terminal,
            "successful": all(s["state"] == "succeeded" for s in snapshots)
            if terminal
            else None,
        },
    }


class Observation:
    """Bounded memory; no durable events, jobs, cursors or polling loops."""

    def __init__(self, *, max_entries: int = 4096, max_bytes: int = 16777216):
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self.cache_sizes = {}
        self.cache_bytes = 0
        self.baseline_sizes = {}
        self.baseline_bytes = 0
        self.cache: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self.baselines: OrderedDict[str, tuple[float, str, dict[str, dict]]] = (
            OrderedDict()
        )
        self.events: deque[dict] = deque()
        self.event_bytes = 0
        self.sequence = 0
        self.instance = uuid.uuid4().hex

    def clear(self) -> None:
        """Invalidate scoped state after destination/config changes."""
        self.cache.clear()
        self.cache_sizes.clear()
        self.cache_bytes = 0
        self.baselines.clear()
        self.baseline_sizes.clear()
        self.baseline_bytes = 0
        self.events.clear()
        self.event_bytes = 0
        self.instance = uuid.uuid4().hex
        self.sequence = 0

    def remember(self, value: dict) -> None:
        """Cache only observations backed by actual native evidence."""
        if value["source"] in {"absent", "unavailable"}:
            return
        identity = key(value["ref"])
        if not self.cache:
            self.cache_sizes.clear()
            self.cache_bytes = 0
        size = len(json.dumps(value).encode())
        self.cache_bytes += size - self.cache_sizes.get(identity, 0)
        self.cache_sizes[identity] = size
        self.cache[identity] = (time.monotonic(), copy.deepcopy(value))
        self.cache.move_to_end(identity)
        while len(self.cache) > self.max_entries or self.cache_bytes > self.max_bytes:
            identity, _ = self.cache.popitem(last=False)
            self.cache_bytes -= self.cache_sizes.pop(identity)

    def cached(self, ref: dict, *, max_age: float | None) -> dict | None:
        """Read a bounded snapshot without treating it as current truth."""
        item = self.cache.get(key(ref))
        if item is None:
            return None
        age = time.monotonic() - item[0]
        if max_age is not None and age > max_age:
            return None
        value = copy.deepcopy(item[1])
        value["freshness"] = {"status": "cached", "age_seconds": age}
        return value

    def observe(self, result: dict, scope: str, cursor: str | None) -> dict:
        """Compute one scoped diff and store only a bounded in-memory baseline."""
        prior = self.baselines.get(cursor or "")
        resync = (
            prior is None or prior[1] != scope or time.monotonic() - prior[0] > 3600
        )
        baseline = {} if resync else prior[2]
        changes = []
        if result["coverage"]["complete"]:
            current = {key(s["ref"]): s for s in result["snapshots"]}
            if not resync:
                for identity, value in current.items():
                    old = baseline.get(identity)
                    if old is None or old["state"] != value["state"]:
                        self.sequence += 1
                        event = {
                            "cursor": f"{self.instance}:{self.sequence}",
                            "observed_at": now(),
                            "ref": value["ref"],
                            "previous_state": old["state"] if old else None,
                            "state": value["state"],
                            "terminal": value["terminal"],
                        }
                        self.events.append(event)
                        self.event_bytes += len(json.dumps(event).encode())
                        while (
                            len(self.events) > 512
                            or self.event_bytes > self.max_bytes // 4
                        ):
                            self.event_bytes -= len(
                                json.dumps(self.events.popleft()).encode()
                            )
                        changes.append(event)
            baseline = current
        token = cursor if not resync else uuid.uuid4().hex
        assert token is not None
        size = len(json.dumps(baseline).encode()) + len(scope.encode())
        self.baseline_bytes += size - self.baseline_sizes.get(token, 0)
        self.baseline_sizes[token] = size
        self.baselines[token] = (time.monotonic(), scope, baseline)
        self.baselines.move_to_end(token)
        while len(self.baselines) > 64 or self.baseline_bytes > self.max_bytes:
            removed, _ = self.baselines.popitem(last=False)
            self.baseline_bytes -= self.baseline_sizes.pop(removed)
        return {**result, "changes": changes, "cursor": token, "resync": resync}

    def since(self, cursor: str | None) -> dict:
        """Read bounded event-ring changes or explicitly require resync."""
        start = self.sequence
        resync = cursor is None
        if cursor:
            try:
                instance, sequence = cursor.rsplit(":", 1)
                start = int(sequence)
                resync = (
                    instance != self.instance
                    or start > self.sequence
                    or start < self.sequence - len(self.events)
                )
            except (ValueError, TypeError):
                resync = True
        return {
            "events": []
            if resync
            else [e for e in self.events if int(e["cursor"].rsplit(":", 1)[1]) > start],
            "cursor": f"{self.instance}:{self.sequence}",
            "resync": resync,
        }
