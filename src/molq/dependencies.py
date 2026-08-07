"""Resolving logical job dependencies into a backend's submit syntax.

molq lets callers express dependencies as *molq* job ids plus a condition
(``after_success`` and friends).  Turning those into the string a scheduler
wants means looking each upstream job up in the store, checking it belongs to
the same destination, and handing the resulting edges to the backend — which
owns the syntax itself (see
:meth:`molq.scheduler.base.Scheduler.format_dependencies`).
"""

from __future__ import annotations

from typing import Any

from molq.errors import ConfigError, JobNotFoundError
from molq.models import JobDependency
from molq.scheduler import DependencyEdge, SchedulerCapabilities
from molq.store import JobStore
from molq.types import DependencyRef


def merge_dependency_refs(
    dependencies: tuple[DependencyRef, ...],
    *,
    after_started: list[str],
    after: list[str],
    after_failure: list[str],
    after_success: list[str],
) -> tuple[DependencyRef, ...]:
    merged = list(dependencies)
    merged.extend(
        DependencyRef(job_id=job_id, condition="after_started")
        for job_id in after_started
    )
    merged.extend(DependencyRef(job_id=job_id, condition="after") for job_id in after)
    merged.extend(
        DependencyRef(job_id=job_id, condition="after_failure")
        for job_id in after_failure
    )
    merged.extend(
        DependencyRef(job_id=job_id, condition="after_success")
        for job_id in after_success
    )
    return tuple(merged)


def resolve_dependencies(
    store: JobStore,
    scheduler: Any,
    capabilities: SchedulerCapabilities,
    cluster_name: str,
    scheduler_name: str,
    *,
    job_id: str,
    root_job_id: str,
    explicit_dependency: str | None,
    dependency_refs: tuple[DependencyRef, ...],
) -> tuple[str | None, list[JobDependency]]:
    if explicit_dependency:
        return explicit_dependency, []
    if not dependency_refs:
        return None, []

    if not capabilities.supports_dependency:
        raise ConfigError(
            f"Scheduler {scheduler_name!r} does not support job dependencies",
            scheduler=scheduler_name,
        )

    seen: set[tuple[str, str]] = set()
    # Edges in submission order; the scheduler renders them into its own
    # submit syntax.
    edges: list[DependencyEdge] = []
    dependencies: list[JobDependency] = []

    for ref in dependency_refs:
        dep_job_id = ref.job_id
        if dep_job_id in {job_id, root_job_id}:
            raise ConfigError(
                "A job cannot depend on itself",
                dependency_job_id=dep_job_id,
            )

        key = (dep_job_id, ref.condition)
        if key in seen:
            continue
        seen.add(key)

        dep_record = store.get_latest_attempt_record(dep_job_id)
        if dep_record is None:
            raise JobNotFoundError(dep_job_id, cluster_name)
        if dep_record.scheduler != scheduler_name:
            raise ConfigError(
                f"Dependency job {dep_job_id!r} belongs to scheduler"
                f" {dep_record.scheduler!r}, not {scheduler_name!r}",
                dependency_job_id=dep_job_id,
            )
        if dep_record.cluster_name != cluster_name:
            raise ConfigError(
                f"Dependency job {dep_job_id!r} belongs to cluster"
                f" {dep_record.cluster_name!r}, not {cluster_name!r}",
                dependency_job_id=dep_job_id,
            )
        if dep_record.scheduler_job_id is None:
            raise ConfigError(
                f"Dependency job {dep_job_id!r} does not have a scheduler job id yet",
                dependency_job_id=dep_job_id,
            )

        edge = DependencyEdge(
            condition=ref.condition,
            scheduler_job_id=dep_record.scheduler_job_id,
        )
        edges.append(edge)
        dependencies.append(
            JobDependency(
                job_id="",
                dependency_job_id=dep_job_id,
                dependency_type=ref.condition,
                scheduler_dependency=scheduler.format_dependency(edge),
            )
        )

    return scheduler.format_dependencies(edges), dependencies
