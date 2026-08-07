"""Event system for job lifecycle notifications.

This module provides a simple pub/sub EventBus that allows registering
callbacks for job status changes. Handlers are called synchronously
but errors in handlers are isolated — a failing callback never breaks
the monitoring loop.
"""

import threading
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import mollog

logger = mollog.get_logger(__name__)


class EventType(StrEnum):
    """Job lifecycle event types."""

    STATUS_CHANGE = "status_change"
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    JOB_CANCELLED = "job_cancelled"
    JOB_TIMEOUT = "job_timeout"
    JOB_TIMED_OUT = "job_timed_out"
    JOB_LOST = "job_lost"
    ALL_COMPLETED = "all_completed"


@dataclass(frozen=True)
class EventPayload:
    """Lifecycle event payload."""

    event: EventType
    job_id: str | None = None
    transition: Any = None
    record: Any = None
    data: Any = None


class EventBus:
    """Pub/sub bus for job lifecycle events.

    Handlers are called synchronously in registration order.
    Exceptions in handlers are logged but do not propagate.
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[Callable]] = defaultdict(list)
        self._lock = threading.Lock()

    def on(self, event: EventType, handler: Callable) -> None:
        """Register a callback for an event type.

        Args:
            event: Event type to listen for.
            handler: Callable that receives the event data.
        """
        with self._lock:
            self._handlers[event].append(handler)

    def off(self, event: EventType, handler: Callable) -> None:
        """Remove a previously registered callback.

        Args:
            event: Event type.
            handler: The handler to remove.
        """
        with self._lock:
            handlers = self._handlers.get(event, [])
            self._handlers[event] = [h for h in handlers if h is not handler]

    def emit(self, event: EventType, data: Any = None) -> None:
        """Dispatch an event to all registered handlers.

        Args:
            event: Event type to emit.
            data: Event payload (StatusChange, JobRecord, or None).
        """
        # Snapshot the handler list under the lock, then dispatch outside it
        # so that handlers may freely on()/off() without deadlocking or
        # mutating the list we are iterating.
        with self._lock:
            handlers = list(self._handlers.get(event, []))
        for handler in handlers:
            try:
                handler(data)
            except Exception:
                handler_name = getattr(handler, "__name__", repr(handler))
                logger.exception(f"Handler {handler_name} failed for event {event}")


#: New state -> the extra lifecycle event it fires alongside STATUS_CHANGE.
_STATE_EVENTS: dict[Any, EventType] = {}


def _state_events() -> dict[Any, EventType]:
    # Built lazily to keep this module free of a molq.status import cycle.
    if not _STATE_EVENTS:
        from molq.status import JobState

        _STATE_EVENTS.update(
            {
                JobState.RUNNING: EventType.JOB_STARTED,
                JobState.SUCCEEDED: EventType.JOB_COMPLETED,
                JobState.FAILED: EventType.JOB_FAILED,
                JobState.CANCELLED: EventType.JOB_CANCELLED,
                JobState.LOST: EventType.JOB_LOST,
            }
        )
    return _STATE_EVENTS


def emit_transition(bus: EventBus, transition: Any, record: Any) -> None:
    """Publish one state transition as the full set of lifecycle events.

    Always emits :attr:`EventType.STATUS_CHANGE`, plus the state-specific
    event for the new state.  ``TIMED_OUT`` fires both
    :attr:`EventType.JOB_TIMED_OUT` and the older
    :attr:`EventType.JOB_TIMEOUT` spelling.

    Both the submit path and the reconcile path funnel through here so a
    subscriber sees the same events regardless of which one moved the job.
    """
    from molq.status import JobState

    new_state = transition.new_state
    payload = EventPayload(
        event=EventType.STATUS_CHANGE,
        job_id=record.job_id,
        transition=transition,
        record=record,
    )
    bus.emit(EventType.STATUS_CHANGE, payload)

    if new_state == JobState.TIMED_OUT:
        timed_out = EventPayload(
            event=EventType.JOB_TIMED_OUT,
            job_id=record.job_id,
            transition=transition,
            record=record,
        )
        bus.emit(EventType.JOB_TIMED_OUT, timed_out)
        bus.emit(EventType.JOB_TIMEOUT, timed_out)
        return

    event = _state_events().get(new_state)
    if event is None:
        return
    bus.emit(
        event,
        EventPayload(
            event=event,
            job_id=record.job_id,
            transition=transition,
            record=record,
        ),
    )
