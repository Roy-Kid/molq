"""Versioned public contract and runtime-only schema validation."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any


@lru_cache(maxsize=1)
def contract() -> dict[str, Any]:
    """Load the packaged language-independent contract."""
    return json.loads(files(__package__).joinpath("v1.json").read_text())


def validate(value: Any, schema: dict[str, Any]) -> None:
    """Validate only inside Runtime, using the canonical JSON Schema."""
    from jsonschema import Draft202012Validator

    from molq.errors import MolqError

    def bounded(item: Any, depth: int = 0) -> None:
        if depth > 64:
            raise MolqError(
                "INVALID_INPUT", "Schema nesting exceeds the protocol bound"
            )
        if isinstance(item, str) and "\x00" in item:
            raise MolqError(
                "INVALID_INPUT",
                "NUL is not legal in target commands, environment or paths",
            )
        if isinstance(item, dict):
            for key, child in item.items():
                bounded(key, depth + 1)
                bounded(child, depth + 1)
        elif isinstance(item, list):
            for child in item:
                bounded(child, depth + 1)

    bounded(value)
    doc = {"$defs": contract()["$defs"], **schema}
    try:
        Draft202012Validator(doc).validate(value)
    except Exception as exc:
        from jsonschema.exceptions import ValidationError

        if not isinstance(exc, ValidationError):
            raise
        raise MolqError(
            "INVALID_INPUT", exc.message, path=list(exc.absolute_path)
        ) from exc
