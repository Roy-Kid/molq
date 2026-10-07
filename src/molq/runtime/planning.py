"""Canonical schema interpretation and execution-tree validation, once."""

from __future__ import annotations

import copy
from typing import Any

from molq.errors import MolqError
from molq.protocol import validate


def normalize(spec: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    """Merge destination defaults and validate a bounded allocation plan."""
    result = copy.deepcopy(spec)
    for section in ("resources", "scheduling"):
        result[section] = {**defaults.get(section, {}), **result.get(section, {})}
    execution = result["execution"]
    execution["env"] = {**defaults.get("env", {}), **execution.get("env", {})}
    if "cwd" not in execution and "cwd" in defaults:
        execution["cwd"] = defaults["cwd"]
    validate(result, {"$ref": "#/$defs/JobSpec"})
    units = execution["units"]
    for unit in units:
        command = unit["command"]
        if command["kind"] == "argv" and not command["argv"][0]:
            raise MolqError("INVALID_INPUT", "argv program must not be empty")
    ids = [u["id"] for u in units]
    if len(set(ids)) != len(ids):
        raise MolqError("INVALID_INPUT", "Execution unit IDs must be unique")
    if "plan" not in execution:
        if len(units) != 1:
            raise MolqError(
                "INVALID_INPUT", "Multiple units require an explicit execution plan"
            )
        execution["plan"] = {"kind": "unit", "ref": ids[0]}
    seen: list[str] = []
    by_id = {u["id"]: u for u in units}

    def visit(plan: dict, depth: int = 0) -> tuple[int, int]:
        if depth > 16:
            raise MolqError("INVALID_INPUT", "Execution plan depth exceeds 16")
        if plan["kind"] == "unit":
            identity = plan["ref"]
            if identity not in by_id:
                raise MolqError(
                    "INVALID_INPUT", "Unknown unit reference", unit=identity
                )
            seen.append(identity)
            unit = by_id[identity]
            launch = unit.get("launch", {"kind": "direct"})
            if launch["kind"] == "mpi" and "ranks" not in launch:
                raise MolqError("INVALID_INPUT", "MPI requires explicit ranks")
            if launch["kind"] == "direct" and (
                "ranks" in launch or "threads" in launch
            ):
                raise MolqError(
                    "INVALID_INPUT", "Direct launch cannot contain MPI layout"
                )
            tasks = launch.get("ranks", unit.get("placement", {}).get("tasks", 1))
            cpus = launch.get(
                "threads", unit.get("placement", {}).get("cpus_per_task", 1)
            )
            if (
                launch["kind"] == "mpi"
                and unit.get("placement", {}).get("tasks", tasks) != tasks
            ):
                raise MolqError(
                    "EXECUTION_RESOURCE_CONFLICT",
                    "MPI ranks and unit placement disagree",
                )
            if (
                launch["kind"] == "mpi"
                and unit.get("placement", {}).get("cpus_per_task", cpus) != cpus
            ):
                raise MolqError(
                    "EXECUTION_RESOURCE_CONFLICT",
                    "MPI threads and unit placement disagree",
                )
            return tasks, tasks * cpus
        budgets = [visit(p, depth + 1) for p in plan["children"]]
        op = sum if plan["kind"] == "parallel" else max
        return op(b[0] for b in budgets), op(b[1] for b in budgets)

    tasks, cpus = visit(execution["plan"])
    if sorted(seen) != sorted(ids):
        raise MolqError(
            "INVALID_INPUT", "Every unit must appear exactly once in the plan"
        )
    resources = result["resources"]
    budget_tasks = resources.get("tasks")
    if budget_tasks is not None and (
        tasks > budget_tasks or cpus > budget_tasks * resources.get("cpus_per_task", 1)
    ):
        raise MolqError(
            "EXECUTION_RESOURCE_CONFLICT",
            "Execution exceeds allocation CPU/task budget",
        )
    if any(
        a["kind"] == "nvidia_mps" and "model" in a
        for a in resources.get("accelerators", [])
    ):
        raise MolqError(
            "RESOURCE_REQUEST_INVALID",
            "MPS resource request cannot specify a GPU model",
        )
    return result
