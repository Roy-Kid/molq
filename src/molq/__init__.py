"""Public API for the molq package.

Usage::

    from molq import Cluster, Submitor, JobResources, Memory

    # Destination — pure config, no lifecycle state.
    cluster  = Cluster("devbox", "local")

    # Lifecycle engine — bound to a target Cluster.
    submitor = Submitor(target=cluster)

    handle = submitor.submit_job(
        argv=["python", "train.py"],
        resources=JobResources(cpu_count=8, memory=Memory.gb(32)),
    )
    print(handle.status())
    record = handle.wait()
    print(record.state)

    # Scheduler-side queue snapshot:
    cluster.get_queue()  # squeue --me / qstat -u $USER / bjobs (or [] for local)
"""

from molq.callbacks import EventBus, EventPayload, EventType
from molq.cluster import Cluster
from molq.config import (
    MolqConfig,
    MolqProfile,
    enabled_plugin_names,
    load_config,
    load_profile,
)
from molq.errors import (
    CommandError,
    ConfigError,
    JobNotFoundError,
    MolqError,
    MolqTimeoutError,
    SchedulerError,
    ScriptError,
    StoreError,
    SubmitError,
)
from molq.models import (
    DependencyPreview,
    DependencyPreviewItem,
    JobDependency,
    JobRecord,
    RememberedAllocation,
    RetentionPolicy,
    RetryBackoff,
    RetryPolicy,
    StatusTransition,
    SubmitorDefaults,
)
from molq.options import (
    LocalSchedulerOptions,
    LSFSchedulerOptions,
    PBSSchedulerOptions,
    SlurmSchedulerOptions,
)
from molq.plugin import (
    BUILTIN_PLUGIN_FACTORIES,
    MolqPlugin,
    PluginContext,
    PluginManager,
    available_plugins,
    create_plugin,
)
from molq.scheduler import QueueEntry, SchedulerCapabilities
from molq.ssh_config import SshHost, list_ssh_hosts, resolve_ssh_host
from molq.status import JobState
from molq.store import dependency_relation_state
from molq.submitor import JobHandle, Submitor
from molq.types import (
    DependencyCondition,
    DependencyRef,
    Duration,
    JobExecution,
    JobResources,
    JobScheduling,
    Memory,
    Script,
)
from molq.workspace import Project, Workspace

__all__ = [
    # Dashboard
    "RunDashboard",
    "MolqMonitor",
    "DashboardState",
    "JobRow",
    "EventBus",
    "EventPayload",
    "EventType",
    # Plugins
    "MolqPlugin",
    "PluginContext",
    "PluginManager",
    "available_plugins",
    "create_plugin",
    "enabled_plugin_names",
    "BUILTIN_PLUGIN_FACTORIES",
    # Core
    "Cluster",
    "Submitor",
    "JobHandle",
    "QueueEntry",
    "Workspace",
    "Project",
    # Types
    "Memory",
    "Duration",
    "Script",
    "DependencyCondition",
    "DependencyRef",
    "JobResources",
    "JobScheduling",
    "JobExecution",
    # Dependency helpers
    "dependency_relation_state",
    # Models
    "SubmitorDefaults",
    "JobRecord",
    "RememberedAllocation",
    "JobDependency",
    "DependencyPreview",
    "DependencyPreviewItem",
    "StatusTransition",
    "RetryBackoff",
    "RetryPolicy",
    "RetentionPolicy",
    "JobState",
    "SchedulerCapabilities",
    # Config
    "MolqConfig",
    "MolqProfile",
    "load_config",
    "load_profile",
    # Options
    "LocalSchedulerOptions",
    "SlurmSchedulerOptions",
    "PBSSchedulerOptions",
    "LSFSchedulerOptions",
    # SSH
    "SshHost",
    "list_ssh_hosts",
    "resolve_ssh_host",
    # Errors
    "MolqError",
    "ConfigError",
    "SubmitError",
    "CommandError",
    "ScriptError",
    "SchedulerError",
    "JobNotFoundError",
    "MolqTimeoutError",
    "StoreError",
]


# ---------------------------------------------------------------------------
# Lazily-loaded names
# ---------------------------------------------------------------------------

#: Dashboard exports, resolved on first attribute access.  ``molq.dashboard``
#: pulls in rich plus termios/tty — a fifth of import time, and Unix-only —
#: which nothing on the submit path needs.
_LAZY_MODULES = {
    "DashboardState": "molq.dashboard",
    "JobRow": "molq.dashboard",
    "MolqMonitor": "molq.dashboard",
    "RunDashboard": "molq.dashboard",
}


def __getattr__(name: str):
    module_name = _LAZY_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    value = getattr(importlib.import_module(module_name), name)
    globals()[name] = value  # cache so later lookups skip this path
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_MODULES))
