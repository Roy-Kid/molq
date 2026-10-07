"""JSON-RPC framing shared by stdio, HTTP and WebSocket input adapters."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from molq.errors import MolqError
from molq.runtime.services import Runtime

MAX_FRAME = 1048576
MUTATIONS = {
    "clusters.register",
    "clusters.update",
    "clusters.remove",
    "jobs.submit",
    "jobs.cancel",
    "jobs.cancel_many",
    "files.write",
    "files.transfer",
    "config.set",
    "presets.set",
}


def error_response(identity: Any, error: MolqError, code: int = -32000) -> dict:
    """Return the same structured error envelope on every channel."""
    return {
        "jsonrpc": "2.0",
        "id": identity,
        "error": {"code": code, "message": str(error), "data": error.to_wire()},
    }


def bounded_response(value: Any) -> Any:
    """Enforce the same output bound on every adapter and batch."""
    if (
        len(json.dumps(value, allow_nan=False, separators=(",", ":")).encode())
        > MAX_FRAME
    ):
        return error_response(
            value.get("id") if isinstance(value, dict) else None,
            MolqError(
                "PARTIAL_FAILURE",
                "RPC response exceeds 1 MiB; narrow the query",
                outcome="unknown",
            ),
        )
    return value


async def dispatch(runtime: Runtime, payload: Any, *, streaming: bool = False) -> Any:
    """Validate envelopes/batches and execute the shared runtime contract."""
    if isinstance(payload, list):
        if not payload or len(payload) > 128:
            return error_response(
                None, MolqError("INVALID_INPUT", "Batch size must be 1..128"), -32600
            )
        responses = await asyncio.gather(
            *(dispatch(runtime, item, streaming=streaming) for item in payload)
        )
        return bounded_response([r for r in responses if r is not None] or None)
    if (
        not isinstance(payload, dict)
        or payload.get("jsonrpc") != "2.0"
        or not isinstance(payload.get("method"), str)
        or (
            "id" in payload
            and (
                isinstance(payload["id"], bool)
                or not isinstance(payload["id"], (str, int, type(None)))
            )
        )
    ):
        return error_response(
            None, MolqError("INVALID_INPUT", "Invalid JSON-RPC envelope"), -32600
        )
    identity = payload.get("id")
    notification = "id" not in payload
    if notification and payload["method"] in MUTATIONS:
        # The public mutation contract requires a correlatable request ID.
        return None
    try:
        params = payload.get("params", {})
        if not isinstance(params, dict):
            raise MolqError("INVALID_INPUT", "Named RPC params must be an object")
        if payload["method"] == "events.subscribe" and not streaming:
            raise MolqError(
                "RPC_CHANNEL_UNSUPPORTED", "Subscriptions require stdio or WebSocket"
            )
        result = await runtime.call(payload["method"], params)
        return (
            None
            if notification
            else bounded_response({"jsonrpc": "2.0", "id": identity, "result": result})
        )
    except MolqError as exc:
        code = (
            -32601
            if exc.kind == "METHOD_NOT_FOUND"
            else -32602
            if exc.kind == "INVALID_INPUT"
            else -32000
        )
        return None if notification else error_response(identity, exc, code)
    except Exception:
        return (
            None
            if notification
            else error_response(
                identity,
                MolqError(
                    "INTERNAL_ERROR",
                    "Runtime operation failed; consult runtime diagnostics",
                    outcome="unknown",
                ),
            )
        )


def decode(frame: bytes | str) -> Any:
    """Reject oversized, nonfinite or malformed frames before dispatch."""
    if len(frame) > MAX_FRAME:
        raise MolqError("INVALID_INPUT", "RPC frame exceeds 1 MiB")
    try:
        return json.loads(
            frame,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ValueError("Nonfinite JSON value")
            ),
        )
    except (ValueError, UnicodeDecodeError, RecursionError) as exc:
        raise MolqError("INVALID_INPUT", "Malformed JSON frame") from exc


async def event_stream(runtime: Runtime, cursor: str):
    """Passively deliver observed changes, including reset, without lost wakeups."""
    while True:
        async with runtime.changed:
            await runtime.changed.wait_for(
                lambda: runtime.observation.since(cursor)["cursor"] != cursor
            )
            result = runtime.observation.since(cursor)
        cursor = result["cursor"]
        yield {"jsonrpc": "2.0", "method": "events", "params": result}


async def stdio(runtime: Runtime) -> None:
    """Serve finite RPC over stdin/stdout and drain dispatched work at EOF.

    A single stdin bridge accommodates ordinary Windows pipes. All business
    operations, target processes, Cluster concurrency and deadlines are async.
    This bridge performs no polling or business/state work.
    """
    subscription = None

    def write(value):
        sys.stdout.write(
            json.dumps(value, allow_nan=False, separators=(",", ":")) + "\n"
        )
        sys.stdout.flush()

    async def send_events(cursor):
        async for event in event_stream(runtime, cursor):
            write(event)

    try:
        while True:
            frame = await asyncio.to_thread(sys.stdin.buffer.readline, MAX_FRAME + 1)
            if not frame:
                return
            payload = None
            try:
                payload = decode(frame)
                response = await dispatch(runtime, payload, streaming=True)
            except MolqError as exc:
                response = error_response(None, exc, -32700)
            if response is not None:
                write(response)
                if (
                    isinstance(payload, dict)
                    and payload.get("method") == "events.subscribe"
                    and isinstance(response, dict)
                    and "result" in response
                ):
                    if subscription:
                        subscription.cancel()
                        await asyncio.gather(subscription, return_exceptions=True)
                    subscription = asyncio.create_task(
                        send_events(response["result"]["cursor"])
                    )
    finally:
        if subscription:
            subscription.cancel()
            await asyncio.gather(subscription, return_exceptions=True)
        await runtime.close()
