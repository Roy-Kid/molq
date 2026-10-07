"""Shared pure Bash plan rendering; native launch mapping stays in Scheduler."""

from __future__ import annotations

import shlex
from collections.abc import Callable
from typing import Any

q = shlex.quote


def render_execution(spec: dict[str, Any], launch: Callable[[dict, str], str]) -> str:
    """Render validated tree semantics into an allocation-internal script."""
    execution = spec["execution"]
    lines: list[str] = []
    names: dict[str, str] = {}
    for index, unit in enumerate(execution["units"]):
        name = f"molq_unit_{index}"
        names[unit["id"]] = name
        command = unit["command"]
        if command["kind"] == "argv":
            payload = shlex.join(command["argv"])
        elif command["kind"] == "shell":
            payload = "bash -c " + q(command["command"])
        else:
            payload = "bash -c " + q(command["text"])
        body = [f"{name}() ("]
        if cwd := unit.get("cwd", execution.get("cwd")):
            body.append(f"cd -- {q(cwd)} || exit 126")
        environment = {**execution.get("env", {}), **unit.get("env", {})}
        body.extend(f"export {key}={q(value)}" for key, value in environment.items())
        if threads := unit.get("launch", {}).get("threads"):
            body.append(f"export OMP_NUM_THREADS={threads}")
        payload = launch(unit, payload)
        for stream, flag in (("stdout", ">"), ("stderr", "2>")):
            if path := unit.get(stream):
                payload += f" {flag} {q(path)}"
        body.extend([payload, ")"])
        lines.extend(body)
    counter = 0

    def emit(plan: dict) -> str:
        nonlocal counter
        if plan["kind"] == "unit":
            return names[plan["ref"]]
        children = [emit(c) for c in plan["children"]]
        name = f"molq_plan_{counter}"
        counter += 1
        lines.append(f"{name}() (")
        if plan["kind"] == "sequence":
            lines.extend(f'{child} || exit "$?"' for child in children)
        else:
            lines.append("pids=(); result=0")
            for child in children:
                lines.extend([f"{child} &", 'pids+=("$!")'])
            lines.extend(
                [
                    'for pid in "${pids[@]}"; do',
                    '  code=0; wait "$pid" || code=$?',
                    '  if [ "$result" -eq 0 ] && [ "$code" -ne 0 ]; then result=$code; fi',
                    "done",
                    'exit "$result"',
                ]
            )
        lines.append(")")
        return name

    root = emit(execution["plan"])
    lines.extend([root, 'exit "$?"'])
    return "\n".join(lines) + "\n"
