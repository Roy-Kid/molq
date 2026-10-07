"""Immutable client value constructors; no rendering or lifecycle logic."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


def _wire(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    if isinstance(value, dict):
        return {k: _wire(v) for k, v in value.items() if v is not None}
    if isinstance(value, (list, tuple)):
        return [_wire(v) for v in value]
    return value


class Value:
    """Project immutable value fields into protocol JSON."""

    def to_wire(self) -> dict[str, Any]:
        """Return fields without defaults merging or semantic interpretation."""
        return _wire(self)


@dataclass(frozen=True)
class Accelerator(Value):
    """A formal allocation resource quantity, with explicit scope."""

    kind: str
    quantity: int
    scope: str = "per_node"
    model: str | None = None


@dataclass(frozen=True)
class Resources(Value):
    """Allocation budget; memory is per-node decimal bytes."""

    nodes: int | None = None
    tasks: int | None = None
    cpus_per_task: int | None = None
    memory_bytes: str | None = None
    time_limit_seconds: int | None = None
    accelerators: tuple[Accelerator, ...] | None = None


@dataclass(frozen=True)
class Scheduling(Value):
    """Scheduling intent, independent of execution content."""

    name: str | None = None
    partition: str | None = None
    account: str | None = None
    qos: str | None = None
    reservation: str | None = None
    priority: int | None = None
    exclusive: bool | None = None
    dependencies: tuple[dict[str, Any], ...] | None = None


@dataclass(frozen=True)
class Launch(Value):
    """Direct or explicitly configured MPI launch intent."""

    kind: str = "direct"
    ranks: int | None = None
    threads: int | None = None


@dataclass(frozen=True)
class ExecutionUnit(Value):
    """One allocation-internal command and optional placement."""

    id: str
    command: dict[str, Any]
    env: dict[str, str] | None = None
    cwd: str | None = None
    stdout: str | None = None
    stderr: str | None = None
    launch: Launch | None = None
    placement: dict[str, int] | None = None

    @classmethod
    def argv(cls, id: str, argv: list[str], **kwargs: Any) -> ExecutionUnit:
        """Construct a command without shell interpretation."""
        return cls(id, {"kind": "argv", "argv": list(argv)}, **kwargs)

    @classmethod
    def shell(cls, id: str, command: str, **kwargs: Any) -> ExecutionUnit:
        """Construct explicit shell content, interpreted only on target."""
        return cls(id, {"kind": "shell", "command": command}, **kwargs)

    @classmethod
    def script(cls, id: str, text: str, **kwargs: Any) -> ExecutionUnit:
        """Construct inline payload script content."""
        return cls(id, {"kind": "script", "text": text}, **kwargs)


@dataclass(frozen=True)
class UnitRef(Value):
    """Reference one execution unit."""

    ref: str
    kind: str = "unit"


@dataclass(frozen=True)
class Sequence(Value):
    """Run child plans in order, stopping on failure."""

    children: tuple[Any, ...]
    kind: str = "sequence"


@dataclass(frozen=True)
class Parallel(Value):
    """Run child plans concurrently, awaiting all started children."""

    children: tuple[Any, ...]
    kind: str = "parallel"


@dataclass(frozen=True)
class Execution(Value):
    """One or more units with an optional compositional plan."""

    units: tuple[ExecutionUnit, ...]
    plan: UnitRef | Sequence | Parallel | None = None
    env: dict[str, str] | None = None
    cwd: str | None = None


@dataclass(frozen=True)
class JobSpec(Value):
    """Orthogonal allocation, scheduling and execution values."""

    execution: Execution
    resources: Resources | None = None
    scheduling: Scheduling | None = None
