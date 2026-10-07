"""Agent-first native CLI; every business operation uses public RPC."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from molq.errors import MolqError


class Parser(argparse.ArgumentParser):
    """Use the shared structured error channel for invalid CLI syntax."""

    def error(self, message):
        raise MolqError("INVALID_INPUT", message)


EXIT_CODES = {
    "INVALID_INPUT": 2,
    "METHOD_NOT_FOUND": 2,
    "CLUSTER_NOT_FOUND": 3,
    "CACHE_MISS": 3,
    "FILE_UNAVAILABLE": 3,
    "RUNTIME_UNAVAILABLE": 4,
    "SCHEDULER_UNAVAILABLE": 4,
    "TRANSPORT_UNAVAILABLE": 4,
    "SCHEDULER_UNSUPPORTED": 5,
    "TRANSFER_UNSUPPORTED": 5,
    "RESOURCE_REQUEST_INVALID": 5,
    "EXECUTION_TOPOLOGY_UNSUPPORTED": 5,
    "EXECUTION_RESOURCE_CONFLICT": 5,
    "RPC_CHANNEL_UNSUPPORTED": 5,
    "WAIT_TIMEOUT": 6,
    "RUNTIME_DEADLINE": 6,
    "AUTH_REQUIRED": 7,
    "PERMISSION_DENIED": 7,
    "SUBMISSION_REJECTED": 7,
    "CANCEL_REJECTED": 7,
    "PARTIAL_FAILURE": 8,
    "OUTCOME_UNKNOWN": 10,
    "CANCEL_OUTCOME_UNKNOWN": 10,
    "CONFLICT": 10,
    "STATE_BUSY": 10,
    "REGISTRY_MISMATCH": 10,
    "JOB_IDENTITY_MISMATCH": 10,
    "JOB_IDENTITY_UNVERIFIABLE": 10,
    "PROTOCOL_MISMATCH": 5,
    "STATE_SCHEMA_INCOMPATIBLE": 5,
}


def parser() -> Parser:
    """Describe commands statically; no Runtime is needed for help/version."""
    p = Parser(
        prog="molq", description="molq 0.9.0: equal RPC clients; JSON output by default"
    )
    p.add_argument("--version", action="version", version="0.9.0")
    p.add_argument("--endpoint", default=os.environ.get("MOLQ_ENDPOINT"))
    p.add_argument("--registry")
    p.add_argument("--token", default=os.environ.get("MOLQ_TOKEN"))
    commands = p.add_subparsers(dest="command", required=True, parser_class=Parser)
    rpc = commands.add_parser("rpc", help="Call any public method with JSON params")
    rpc.add_argument("method")
    rpc.add_argument(
        "--params", default="{}", help="JSON object, @file, or @- for stdin"
    )
    discover = commands.add_parser(
        "discover", help="Print canonical methods and schemas"
    )
    discover.set_defaults(method="schema.discover")
    clusters = commands.add_parser(
        "clusters", help="Register/list/get/update/remove destinations"
    )
    c = clusters.add_subparsers(dest="action", required=True, parser_class=Parser)
    c.add_parser("list")
    register = c.add_parser("register")
    register.add_argument("--definition", required=True)
    get = c.add_parser("get")
    get.add_argument("cluster")
    update = c.add_parser("update")
    update.add_argument("cluster")
    update.add_argument("--definition", required=True)
    update.add_argument("--revision", type=int, required=True)
    remove = c.add_parser("remove")
    remove.add_argument("cluster")
    remove.add_argument("--revision", type=int, required=True)
    submit = commands.add_parser(
        "submit", help="Submit a canonical spec or single argv allocation"
    )
    submit.add_argument("cluster")
    submit.add_argument("--spec")
    submit.add_argument("--request-key")
    submit.add_argument("argv", nargs="*")
    for name in ("status", "cancel", "logs", "wait"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--ref", required=True, help="JSON JobRef, @file, or @-")
        if name == "status":
            cmd.add_argument(
                "--consistency", choices=["live", "bounded", "cached"], default="live"
            )
        if name == "logs":
            cmd.add_argument("--stream", choices=["stdout", "stderr"], default="stdout")
            cmd.add_argument("--offset", type=int, default=0)
            cmd.add_argument("--limit", type=int, default=262144)
        if name == "wait":
            cmd.add_argument("--timeout", type=float, default=3600)
            cmd.add_argument("--interval", type=float, default=1)
    listing = commands.add_parser("list")
    listing.add_argument("cluster")
    observe = commands.add_parser("observe")
    observe.add_argument("cluster")
    observe.add_argument("--cursor")
    runtime = commands.add_parser(
        "runtime", help="Explicit Runtime process entry points"
    )
    r = runtime.add_subparsers(dest="action", required=True, parser_class=Parser)
    stdio = r.add_parser("rpc")
    stdio.add_argument("--stdio", action="store_true", required=True)
    stdio.add_argument("--registry")
    serve = r.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=17891)
    serve.add_argument("--registry")
    serve.add_argument("--token", default=os.environ.get("MOLQ_TOKEN"))
    observer = commands.add_parser(
        "observer", help="Optional client-only periodic observation"
    )
    observer.add_argument("--interval", type=float, default=5)
    observer.add_argument("--cluster", action="append")
    observer.add_argument("--once", action="store_true")
    observer.add_argument("--nerve-endpoint")
    return p


def read_json(value: str):
    """Read a literal/file/stdin payload without hiding parse errors."""
    try:
        text = (
            sys.stdin.read()
            if value == "@-"
            else Path(value[1:]).read_text()
            if value.startswith("@")
            else value
        )
        return json.loads(text)
    except (ValueError, OSError) as exc:
        raise MolqError("INVALID_INPUT", "Cannot read JSON input") from exc


def emit(value: dict) -> None:
    """Emit exactly one JSON line; streaming commands use the same envelopes."""
    print(json.dumps(value, allow_nan=False, separators=(",", ":")), flush=True)


def _business(args) -> dict:
    import time

    from molq.client.wire import Wire
    from molq.domain import Execution, ExecutionUnit, JobSpec

    wire = Wire(endpoint=args.endpoint, registry=args.registry, token=args.token)

    def call(method, **params):
        return wire.call(method, {k: v for k, v in params.items() if v is not None})

    try:
        command = args.command
        if command in {"rpc", "discover"}:
            return call(
                args.method, **(read_json(args.params) if command == "rpc" else {})
            )
        if command == "clusters":
            if args.action == "register":
                params = read_json(args.definition)
            else:
                params = {} if args.action == "list" else {"cluster": args.cluster}
                if args.action in {"update", "remove"}:
                    params["expected_revision"] = args.revision
                if args.action == "update":
                    params["definition"] = read_json(args.definition)
            return call("clusters." + args.action, **params)
        if command == "submit":
            argv = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
            if bool(args.spec) == bool(argv):
                raise MolqError("INVALID_INPUT", "Provide exactly one of spec or argv")
            spec = (
                read_json(args.spec)
                if args.spec
                else JobSpec(Execution((ExecutionUnit.argv("main", argv),))).to_wire()
            )
            return call(
                "jobs.submit",
                cluster=args.cluster,
                spec=spec,
                request_key=args.request_key,
            )
        if command in {"list", "observe"}:
            return call(
                "jobs." + command,
                cluster=args.cluster,
                **({"cursor": args.cursor} if command == "observe" else {}),
            )
        ref = read_json(args.ref)
        if command == "status":
            return call("jobs.get", ref=ref, consistency=args.consistency)
        if command == "cancel":
            return call("jobs.cancel", ref=ref)
        if command == "logs":
            return call(
                "logs.read",
                ref=ref,
                stream=args.stream,
                offset=args.offset,
                limit=args.limit,
            )
        if args.timeout <= 0 or args.interval <= 0:
            raise MolqError("INVALID_INPUT", "wait timeout/interval must be positive")
        deadline = time.monotonic() + args.timeout
        cursor = None
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise MolqError("WAIT_TIMEOUT", "Foreground wait deadline reached")
            wire.timeout = min(130, remaining)
            result = call("jobs.observe", refs=[ref], cursor=cursor)
            cursor = result["cursor"]
            if result["completion"]["all_confirmed_terminal"]:
                return result
            time.sleep(min(args.interval, max(0, deadline - time.monotonic())))
    finally:
        wire.close()


def main() -> None:
    """Run business via RPC; process entry commands own only assembly."""
    try:
        args = parser().parse_args()
        if args.command == "runtime":
            from molq.registry import default_registry
            from molq.runtime import Runtime

            runtime = Runtime(
                Path(args.registry) if args.registry else default_registry()
            )
            if args.action == "rpc":
                from molq.runtime.rpc import stdio

                asyncio.run(stdio(runtime))
            else:
                from aiohttp import web

                from molq.runtime.server import application

                try:
                    app = application(runtime, args.token or "")
                except BaseException:
                    asyncio.run(runtime.close())
                    raise
                web.run_app(app, host=args.host, port=args.port, print=None)
            return
        if args.command == "observer":
            from molq.observer import run

            asyncio.run(
                run(
                    endpoint=args.endpoint,
                    registry=args.registry,
                    token=args.token,
                    clusters=args.cluster,
                    interval=args.interval,
                    once=args.once,
                    nerve_endpoint=args.nerve_endpoint,
                )
            )
            return
        result = _business(args)
        emit({"jsonrpc": "2.0", "id": 1, "result": result})
        if (
            isinstance(result, dict)
            and result.get("completion", {}).get("successful") is False
        ):
            raise SystemExit(9)
        if isinstance(result, dict) and (
            result.get("partial_failure") or result.get("coverage", {}).get("errors")
        ):
            raise SystemExit(8)
    except MolqError as exc:
        emit(
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32000, "message": str(exc), "data": exc.to_wire()},
            }
        )
        raise SystemExit(EXIT_CODES.get(exc.kind, 1)) from None
    except KeyboardInterrupt:
        emit(
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32000,
                    "message": "Interrupted",
                    "data": MolqError(
                        "INTERRUPTED", "Interrupted", outcome="unknown"
                    ).to_wire(),
                },
            }
        )
        raise SystemExit(130) from None
    except (OSError, ValueError, TypeError) as exc:
        error = MolqError("INVALID_INPUT", str(exc))
        emit(
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32000,
                    "message": str(error),
                    "data": error.to_wire(),
                },
            }
        )
        raise SystemExit(2) from None
