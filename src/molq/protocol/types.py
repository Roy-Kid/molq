"""Generated from protocol/v1.json; edit its declarative source."""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


class Command0(TypedDict):
    """Canonical wire shape."""

    kind: Literal["argv"]
    argv: list[str]


class Command1(TypedDict):
    """Canonical wire shape."""

    kind: Literal["shell"]
    command: str


class Command2(TypedDict):
    """Canonical wire shape."""

    kind: Literal["script"]
    text: str


Command = Command0 | Command1 | Command2


class Accelerator(TypedDict):
    """Canonical wire shape."""

    kind: Literal["gpu", "nvidia_mps"]
    quantity: int
    scope: Literal["per_node", "total"]
    model: NotRequired[str]


class Resources(TypedDict):
    """Canonical wire shape."""

    nodes: NotRequired[int]
    tasks: NotRequired[int]
    cpus_per_task: NotRequired[int]
    memory_bytes: NotRequired[str]
    time_limit_seconds: NotRequired[int]
    accelerators: NotRequired[list[Accelerator]]


class JobRef(TypedDict):
    """Canonical wire shape."""

    registry_id: str
    cluster_id: str
    native_id: str
    incarnation: str


class Dependency(TypedDict):
    """Canonical wire shape."""

    ref: JobRef
    condition: Literal["after", "after_success", "after_failure", "after_started"]


class Scheduling(TypedDict):
    """Canonical wire shape."""

    name: NotRequired[str]
    partition: NotRequired[str]
    account: NotRequired[str]
    qos: NotRequired[str]
    reservation: NotRequired[str]
    priority: NotRequired[int]
    exclusive: NotRequired[bool]
    dependencies: NotRequired[list[Dependency]]


class Launch(TypedDict):
    """Canonical wire shape."""

    kind: Literal["direct", "mpi"]
    ranks: NotRequired[int]
    threads: NotRequired[int]


class Placement(TypedDict):
    """Canonical wire shape."""

    tasks: NotRequired[int]
    cpus_per_task: NotRequired[int]


class ExecutionUnit(TypedDict):
    """Canonical wire shape."""

    id: str
    command: Command
    env: NotRequired[dict[str, str]]
    cwd: NotRequired[str]
    stdout: NotRequired[str]
    stderr: NotRequired[str]
    launch: NotRequired[Launch]
    placement: NotRequired[Placement]


class Plan0(TypedDict):
    """Canonical wire shape."""

    kind: Literal["unit"]
    ref: str


class Plan1(TypedDict):
    """Canonical wire shape."""

    kind: Literal["sequence", "parallel"]
    children: list[Plan]


Plan = Plan0 | Plan1


class Execution(TypedDict):
    """Canonical wire shape."""

    units: list[ExecutionUnit]
    plan: NotRequired[Plan]
    env: NotRequired[dict[str, str]]
    cwd: NotRequired[str]


class JobSpec(TypedDict):
    """Canonical wire shape."""

    resources: NotRequired[Resources]
    scheduling: NotRequired[Scheduling]
    execution: Execution


class Defaults(TypedDict):
    """Canonical wire shape."""

    resources: NotRequired[Resources]
    scheduling: NotRequired[Scheduling]
    env: NotRequired[dict[str, str]]
    cwd: NotRequired[str]


class TransportDefinition0(TypedDict):
    """Canonical wire shape."""

    kind: Literal["local"]


class TransportDefinition1(TypedDict):
    """Canonical wire shape."""

    kind: Literal["ssh"]
    alias: str


TransportDefinition = TransportDefinition0 | TransportDefinition1


class ClusterDefinition(TypedDict):
    """Canonical wire shape."""

    name: str
    scheduler: Literal["shell", "slurm", "pbs", "lsf"]
    transport: NotRequired[TransportDefinition]
    target_root: str
    defaults: NotRequired[Defaults]
    launcher: NotRequired[Literal["srun", "mpirun", "mpiexec"]]
    pbs_dialect: NotRequired[Literal["openpbs"]]


class ErrorData(TypedDict):
    """Canonical wire shape."""

    kind: str
    message: str
    outcome: Literal["not_applied", "applied", "unknown"]
    context: dict[str, Any]


class Freshness(TypedDict):
    """Canonical wire shape."""

    status: Literal["live", "cached", "stale", "unavailable"]
    age_seconds: float


class Completion(TypedDict):
    """Canonical wire shape."""

    all_confirmed_terminal: bool
    successful: bool | None


class JobSnapshot(TypedDict):
    """Canonical wire shape."""

    ref: JobRef
    state: Literal[
        "queued", "running", "succeeded", "failed", "cancelled", "timed_out", "unknown"
    ]
    terminal: bool
    observed_at: str
    freshness: Freshness
    source: Literal["queue", "accounting", "shell_receipt", "absent", "unavailable"]
    raw_state: str
    exit_code: int | None
    error: NotRequired[ErrorData]
    last_known: NotRequired[JobSnapshot]


class Coverage(TypedDict):
    """Canonical wire shape."""

    complete: bool
    errors: list[ErrorData]


class ObservedChange(TypedDict):
    """Canonical wire shape."""

    cursor: str
    observed_at: str
    ref: JobRef
    previous_state: str | None
    state: str
    terminal: bool


class ObservationResult(TypedDict):
    """Canonical wire shape."""

    snapshots: list[JobSnapshot]
    coverage: Coverage
    completion: Completion
    changes: NotRequired[list[ObservedChange]]
    cursor: NotRequired[str]
    resync: NotRequired[bool]


class ClusterRecord(TypedDict):
    """Canonical wire shape."""

    name: str
    scheduler: Literal["shell", "slurm", "pbs", "lsf"]
    transport: NotRequired[TransportDefinition]
    target_root: str
    defaults: NotRequired[Defaults]
    launcher: NotRequired[Literal["srun", "mpirun", "mpiexec"]]
    pbs_dialect: NotRequired[Literal["openpbs"]]
    id: str
    revision: int


class MolqHelloParams(TypedDict):
    """Canonical wire shape."""

    pass


class SchemaDiscoverParams(TypedDict):
    """Canonical wire shape."""

    pass


class ClustersListParams(TypedDict):
    """Canonical wire shape."""

    pass


class ClustersGetParams(TypedDict):
    """Canonical wire shape."""

    cluster: str


ClustersRegisterParams = ClusterDefinition


class ClustersUpdateParams(TypedDict):
    """Canonical wire shape."""

    cluster: str
    definition: ClusterDefinition
    expected_revision: int


class ClustersRemoveParams(TypedDict):
    """Canonical wire shape."""

    cluster: str
    expected_revision: int


class JobsValidateParams(TypedDict):
    """Canonical wire shape."""

    cluster: str
    spec: JobSpec


class JobsPreviewParams(TypedDict):
    """Canonical wire shape."""

    cluster: str
    spec: JobSpec


class JobsSubmitParams(TypedDict):
    """Canonical wire shape."""

    cluster: str
    spec: JobSpec
    request_key: NotRequired[str]


class JobsGetParams(TypedDict):
    """Canonical wire shape."""

    ref: JobRef
    consistency: NotRequired[Literal["live", "bounded", "cached"]]
    max_age: NotRequired[float]


class JobsGet_ManyParams(TypedDict):
    """Canonical wire shape."""

    refs: list[JobRef]
    consistency: NotRequired[Literal["live", "bounded", "cached"]]
    max_age: NotRequired[float]


class JobsObserveParams(TypedDict):
    """Canonical wire shape."""

    refs: NotRequired[list[JobRef]]
    consistency: NotRequired[Literal["live", "bounded", "cached"]]
    max_age: NotRequired[float]
    cluster: NotRequired[str]
    cursor: NotRequired[str]


class JobsListParams(TypedDict):
    """Canonical wire shape."""

    cluster: str


class JobsHistoryParams(TypedDict):
    """Canonical wire shape."""

    cluster: str
    refs: list[JobRef]


class JobsCancelParams(TypedDict):
    """Canonical wire shape."""

    ref: JobRef
    request_key: NotRequired[str]


class JobsCancel_ManyParams(TypedDict):
    """Canonical wire shape."""

    refs: list[JobRef]


class LogsReadParams(TypedDict):
    """Canonical wire shape."""

    ref: JobRef
    stream: NotRequired[Literal["stdout", "stderr"]]
    offset: NotRequired[int]
    limit: NotRequired[int]


class FilesReadParams(TypedDict):
    """Canonical wire shape."""

    cluster: str
    path: str
    offset: NotRequired[int]
    limit: NotRequired[int]


class FilesWriteParams(TypedDict):
    """Canonical wire shape."""

    cluster: str
    path: str
    offset: NotRequired[int]
    data: str


class FilesTransferParams(TypedDict):
    """Canonical wire shape."""

    source_cluster: str
    source_path: str
    destination_cluster: str
    destination_path: str


class ConfigGetParams(TypedDict):
    """Canonical wire shape."""

    key: str


class ConfigSetParams(TypedDict):
    """Canonical wire shape."""

    key: str
    value: Any


class PresetsListParams(TypedDict):
    """Canonical wire shape."""

    pass


class PresetsGetParams(TypedDict):
    """Canonical wire shape."""

    key: str


class PresetsSetParams(TypedDict):
    """Canonical wire shape."""

    key: str
    value: Defaults


class EventsSubscribeParams(TypedDict):
    """Canonical wire shape."""

    cursor: NotRequired[str]
