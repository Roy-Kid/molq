"""Lazy logger acquisition.

``mollog`` pulls in ``logfire``, which costs roughly 200 ms — most of what
``import molq`` used to spend. Nothing on a normal submit path logs anything,
so that price should be paid on the first log call, not on import.

Use exactly as before::

    from molq._log import get_logger

    logger = get_logger(__name__)
"""

from __future__ import annotations

from typing import Any


class _LazyLogger:
    """Stands in for a mollog logger until an attribute is actually used."""

    __slots__ = ("_name", "_logger")

    def __init__(self, name: str) -> None:
        self._name = name
        self._logger: Any = None

    def _resolve(self) -> Any:
        if self._logger is None:
            import mollog

            self._logger = mollog.get_logger(self._name)
        return self._logger

    def __getattr__(self, attribute: str) -> Any:
        # Only reached for names that are not slots, i.e. every logging call.
        return getattr(self._resolve(), attribute)

    def __repr__(self) -> str:
        state = "resolved" if self._logger is not None else "deferred"
        return f"<lazy logger {self._name!r} ({state})>"


def get_logger(name: str) -> Any:
    """Return a logger that imports ``mollog`` on first use."""
    return _LazyLogger(name)
