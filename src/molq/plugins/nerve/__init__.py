"""Official Nerve plugin — push molq job status to the local Nerve hub.

Posts rollup snapshots to ``http://127.0.0.1:17890/v1/snapshot`` so hundreds
of jobs become one batch/chain row (leaves only when few, or when attention).

Config keys under ``[plugins.nerve]`` (all optional)::

    enabled = true
    expand_threshold = 8
    debounce_seconds = 0.3
    ingest_url = "http://127.0.0.1:17890"
    show_members = "attention"   # never | attention | all  (ingest hint)
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import mollog

from molq.callbacks import EventPayload, EventType
from molq.models import JobRecord
from molq.plugin import MolqPlugin, PluginContext
from molq.plugins.nerve.mapping import (
    build_snapshots,
    machine_alias,
    machine_kind,
)

logger = mollog.get_logger(__name__)

DEFAULT_INGEST = "http://127.0.0.1:17890"
DEFAULT_EXPAND_THRESHOLD = 8
DEFAULT_DEBOUNCE_SECONDS = 0.3


def create_plugin() -> MolqPlugin:
    """Entry factory for the plugin host."""
    return NervePlugin()


@dataclass
class _Tracked:
    record: JobRecord
    updated_at: float


class NervePlugin:
    """Subscribe to STATUS_CHANGE; POST rollup snapshots to Nerve (fail-open)."""

    name = "nerve"

    def __init__(self) -> None:
        self._ctx: PluginContext | None = None
        self._handler: Any = None
        self._lock = threading.Lock()
        self._tracked: dict[str, _Tracked] = {}
        self._timer: threading.Timer | None = None
        self._version = 0
        self._expand_threshold = DEFAULT_EXPAND_THRESHOLD
        self._debounce = DEFAULT_DEBOUNCE_SECONDS
        self._ingest_base = DEFAULT_INGEST
        self._show_members = "attention"
        self._alias = machine_alias()
        self._machine_kind = machine_kind()

    def attach(self, ctx: PluginContext) -> None:
        self.detach()
        self._ctx = ctx
        cfg = ctx.config
        self._expand_threshold = int(
            cfg.get("expand_threshold", DEFAULT_EXPAND_THRESHOLD)
        )
        self._debounce = float(cfg.get("debounce_seconds", DEFAULT_DEBOUNCE_SECONDS))
        self._ingest_base = str(cfg.get("ingest_url", DEFAULT_INGEST)).rstrip("/")
        self._show_members = str(cfg.get("show_members", "attention")).lower()
        if "alias" in cfg and cfg["alias"]:
            self._alias = str(cfg["alias"])

        # Seed from currently active records so daemon attach is not blank.
        try:
            for rec in ctx.list_active_records():
                self._tracked[rec.job_id] = _Tracked(record=rec, updated_at=time.time())
        except Exception:
            logger.exception("nerve: seed active records failed")

        self._handler = self._on_event
        ctx.event_bus.on(EventType.STATUS_CHANGE, self._handler)
        self._schedule_flush()

    def detach(self) -> None:
        with self._lock:
            timer = self._timer
            self._timer = None
        if timer is not None:
            timer.cancel()
        ctx = self._ctx
        handler = self._handler
        if ctx is not None and handler is not None:
            try:
                ctx.event_bus.off(EventType.STATUS_CHANGE, handler)
            except Exception:
                logger.exception("nerve: off STATUS_CHANGE failed")
        # Best-effort: end open groups so rows leave the panel.
        try:
            self._flush(force_end=True)
        except Exception:
            logger.exception("nerve: detach flush failed")
        self._ctx = None
        self._handler = None
        with self._lock:
            self._tracked.clear()

    def _on_event(self, data: Any) -> None:
        try:
            payload = data if isinstance(data, EventPayload) else None
            record = getattr(payload, "record", None) if payload else None
            if not isinstance(record, JobRecord):
                return
            with self._lock:
                self._tracked[record.job_id] = _Tracked(
                    record=record, updated_at=time.time()
                )
            self._schedule_flush()
        except Exception:
            logger.exception("nerve: status handler failed")

    def _schedule_flush(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            timer = threading.Timer(self._debounce, self._flush_safe)
            timer.daemon = True
            self._timer = timer
            timer.start()

    def _flush_safe(self) -> None:
        try:
            self._flush(force_end=False)
        except Exception:
            logger.exception("nerve: flush failed")

    def _flush(self, *, force_end: bool) -> None:
        with self._lock:
            tracked = {jid: t.record for jid, t in self._tracked.items()}
            self._version += 1
            version = self._version

        if not tracked and not force_end:
            return

        cluster = self._ctx.cluster_name if self._ctx else "unknown"
        snaps = build_snapshots(
            records=list(tracked.values()),
            cluster_name=cluster,
            expand_threshold=self._expand_threshold,
            show_members=self._show_members,
            version=version,
            force_end=force_end,
            alias=self._alias,
        )
        if not snaps:
            return

        body = {
            "alias": self._alias,
            "machineKind": self._machine_kind,
            "jobs": snaps,
        }
        self._post_snapshot(body)

        # Drop terminal leaves after reporting so memory stays bounded.
        with self._lock:
            for jid, rec in list(self._tracked.items()):
                if rec.record.state.is_terminal:
                    # Keep failed/attention a bit? For now drop all terminal after flush.
                    del self._tracked[jid]

    def _post_snapshot(self, body: dict[str, Any]) -> None:
        url = urljoin(self._ingest_base + "/", "v1/snapshot")
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "User-Agent": "molq-nerve/0.1",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=0.5) as resp:
                resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.debug(f"nerve: ingest unavailable ({exc})")
        except Exception:
            logger.debug("nerve: ingest POST failed", exc_info=True)
