"""Submit-time validation of a job request against a backend's capabilities.

Kept apart from :mod:`molq.submitor` because it is a pure function of the spec
and the capability matrix — no store, no scheduler, no I/O — which makes the
support table for every backend directly testable.
"""

from __future__ import annotations

from molq.errors import ConfigError
from molq.models import JobSpec
from molq.scheduler import SchedulerCapabilities
from molq.types import JobExecution

#: ``(field label, spec accessor, capability attribute)`` for every request
#: field a backend may decline.  Data rather than code so adding a field is a
#: one-line change and the whole matrix is visible at a glance.
_CHECKS: tuple[tuple[str, str, str], ...] = (
    ("execution.job_name", "job_name", "supports_job_name"),
    ("execution.output_file", "output_file", "supports_output_file"),
    ("execution.error_file", "error_file", "supports_error_file"),
    ("resources.cpu_count", "cpu_count", "supports_cpu_count"),
    ("resources.memory", "memory", "supports_memory"),
    ("resources.gpu_count", "gpu_count", "supports_gpu_count"),
    ("resources.gpu_type", "gpu_type", "supports_gpu_type"),
    ("resources.time_limit", "time_limit", "supports_time_limit"),
    ("scheduling.partition", "partition", "supports_partition"),
    ("scheduling.account", "account", "supports_account"),
    ("scheduling.priority", "priority", "supports_priority"),
    ("scheduling.dependency", "dependency", "supports_dependency"),
    ("scheduling.node_count", "node_count", "supports_node_count"),
    ("scheduling.array_spec", "array_spec", "supports_array_jobs"),
    ("scheduling.email", "email", "supports_email"),
    ("scheduling.qos", "qos", "supports_qos"),
    ("scheduling.reservation", "reservation", "supports_reservation"),
)


def validate_spec(
    spec: JobSpec,
    capabilities: SchedulerCapabilities,
    *,
    requested_execution: JobExecution,
    scheduler_name: str,
) -> None:
    """Reject a spec that asks for something the backend cannot express.

    Args:
        spec: The canonical job spec about to be submitted.
        capabilities: The backend's declared support matrix.
        requested_execution: The execution block *as the caller supplied it*.
            ``spec.execution`` has already been filled in with a resolved cwd
            and default log paths, so ``cwd``/``env`` support must be judged
            against what was actually asked for.
        scheduler_name: Backend name, for the error message.

    Raises:
        ConfigError: Listing every unsupported field at once, so a caller
            fixes them in one pass instead of one error per round trip.
    """
    unsupported: list[str] = []

    def require(field: str, supported: bool, requested: bool) -> None:
        if requested and not supported:
            unsupported.append(field)

    # cwd and env are judged on the request, not the resolved spec.
    require(
        "execution.cwd", capabilities.supports_cwd, requested_execution.cwd is not None
    )
    require("execution.env", capabilities.supports_env, bool(requested_execution.env))

    sources = {
        "execution": spec.execution,
        "resources": spec.resources,
        "scheduling": spec.scheduling,
    }
    for label, attribute, capability in _CHECKS:
        group, _, _ = label.partition(".")
        value = getattr(sources[group], attribute)
        # exclusive_node is a bool flag: "requested" means True, not "set".
        requested = bool(value) if isinstance(value, bool) else value is not None
        require(label, getattr(capabilities, capability), requested)

    require(
        "scheduling.exclusive_node",
        capabilities.supports_exclusive_node,
        spec.scheduling.exclusive_node,
    )

    if unsupported:
        fields = ", ".join(unsupported)
        raise ConfigError(
            f"Scheduler {scheduler_name!r} does not support requested fields: {fields}",
            scheduler=scheduler_name,
            unsupported_fields=tuple(unsupported),
        )


def default_capabilities() -> SchedulerCapabilities:
    """Permissive matrix for a backend that declares no ``capabilities()``.

    A custom Scheduler that predates the capability protocol should not have
    its users' requests rejected, so assume everything is supported.
    """
    return SchedulerCapabilities(
        supports_cwd=True,
        supports_env=True,
        supports_output_file=True,
        supports_error_file=True,
        supports_job_name=True,
        supports_cpu_count=True,
        supports_memory=True,
        supports_gpu_count=True,
        supports_gpu_type=True,
        supports_time_limit=True,
        supports_partition=True,
        supports_account=True,
        supports_priority=True,
        supports_dependency=True,
        supports_node_count=True,
        supports_exclusive_node=True,
        supports_array_jobs=True,
        supports_email=True,
        supports_qos=True,
        supports_reservation=True,
    )
