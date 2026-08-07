"""Job persistence for molq.

SQLite-backed, WAL mode, UUID job identity, schema versioning.

Layout:
  * :mod:`molq.store.jobstore` — the :class:`JobStore` query surface
  * :mod:`molq.store.schema`   — DDL constants and the migration ladder
  * :mod:`molq.store.records`  — row mapping and dependency evaluation
"""

from __future__ import annotations

from molq.store.jobstore import JobStore, default_jobs_db_path
from molq.store.records import dependency_relation_state

__all__ = [
    "JobStore",
    "default_jobs_db_path",
    "dependency_relation_state",
]
