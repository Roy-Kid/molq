"""RPC codec and native connection management; no molq business behavior."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path
from typing import Any

from molq.errors import MolqError

MAX_FRAME = 1048576


class Wire:
    """One stdio session or an explicit authenticated HTTP endpoint."""

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        registry: Path | str | None = None,
        token: str | None = None,
        timeout: float = 130,
        registry_id: str | None = None,
    ):
        self.endpoint = endpoint or os.environ.get("MOLQ_ENDPOINT")
        self.registry = registry
        self.token = token or os.environ.get("MOLQ_TOKEN")
        self.timeout = timeout
        self.registry_id = registry_id
        self.process: subprocess.Popen | None = None
        self.events = deque(maxlen=128)
        self.sequence = 0
        self.lock = threading.Lock()
        self.hello: dict | None = None

    def _start(self) -> None:
        if self.process is not None:
            return
        argv = [sys.executable, "-m", "molq", "runtime", "rpc", "--stdio"]
        if self.registry is not None:
            argv.extend(["--registry", str(self.registry)])
        # stdout is protocol-only; stderr is diagnostic and cannot fill a pipe.
        self.process = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None
        )

    def connect(self) -> dict:
        """Verify protocol and optional registry identity before any business call."""
        if self.hello is None:
            hello = self._request("molq.hello", {})
            if hello["version"]["major"] != 1:
                raise MolqError("PROTOCOL_MISMATCH", "Incompatible RPC major version")
            if self.registry_id and hello["registry_id"] != self.registry_id:
                raise MolqError(
                    "REGISTRY_MISMATCH", "Endpoint serves a different registry"
                )
            self.hello = hello
        return self.hello

    def call(self, method: str, params: dict | None = None) -> Any:
        """Send one operation without renderer, defaults merge or state logic."""
        with self.lock:
            if method != "molq.hello":
                self.connect()
            return self._request(method, params or {})

    def _request(self, method: str, params: dict) -> Any:
        self.sequence += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self.sequence,
            "method": method,
            "params": params,
        }
        data = json.dumps(payload, allow_nan=False, separators=(",", ":")).encode()
        if len(data) > MAX_FRAME:
            raise MolqError("INVALID_INPUT", "RPC frame exceeds 1 MiB")
        mutation = method in {
            "clusters.register",
            "clusters.update",
            "clusters.remove",
            "config.set",
            "presets.set",
            "jobs.submit",
            "jobs.cancel",
            "jobs.cancel_many",
            "files.write",
            "files.transfer",
        }
        try:
            if self.endpoint:
                request = urllib.request.Request(
                    self.endpoint.rstrip("/") + "/rpc",
                    data=data,
                    headers={
                        "Content-Type": "application/json",
                        **(
                            {"Authorization": "Bearer " + self.token}
                            if self.token
                            else {}
                        ),
                    },
                )
                try:
                    with urllib.request.urlopen(
                        request, timeout=self.timeout
                    ) as response:
                        frame = response.read(MAX_FRAME + 1)
                except urllib.error.HTTPError as exc:
                    frame = exc.read(MAX_FRAME + 1)
            else:
                self._start()
                assert self.process and self.process.stdin and self.process.stdout
                self.process.stdin.write(data + b"\n")
                self.process.stdin.flush()
                # One finite read bridge supports Windows ordinary pipes too.
                stdout = self.process.stdout
                value: list[bytes | BaseException] = []

                def read():
                    try:
                        while True:
                            received = stdout.readline(MAX_FRAME + 1)
                            if not received or len(received) > MAX_FRAME:
                                raise OSError("Invalid frame length")
                            decoded = json.loads(received)
                            if (
                                decoded.get("method") == "events"
                                and "id" not in decoded
                            ):
                                self.events.append(decoded["params"])
                                continue
                            value.append(received)
                            break
                    except BaseException as exc:
                        value.append(exc)

                reader = threading.Thread(target=read, daemon=True)
                reader.start()
                reader.join(self.timeout)
                if reader.is_alive():
                    self.process.kill()
                    self.process.wait(timeout=5)
                    reader.join(5)
                    raise TimeoutError("RPC response deadline")
                if not value or isinstance(value[0], BaseException):
                    raise OSError("RPC pipe closed")
                frame = value[0]
            if not frame or len(frame) > MAX_FRAME:
                raise OSError("Empty/oversized RPC response")
            response = json.loads(frame)
            if (
                response.get("id") != self.sequence
                and not (response.get("id") is None and "error" in response)
            ) or response.get("jsonrpc") != "2.0":
                raise OSError("RPC response identity mismatch")
            if "error" in response:
                raise MolqError.from_wire(response["error"]["data"])
            return response["result"]
        except (OSError, ValueError, KeyError, TimeoutError) as exc:
            raise MolqError(
                "OUTCOME_UNKNOWN" if mutation else "RUNTIME_UNAVAILABLE",
                "RPC connection failed",
                outcome="unknown" if mutation else "not_applied",
            ) from exc

    def close(self) -> None:
        """Close only this session; accepted jobs and user SSH masters survive."""
        if self.process:
            if self.process.stdin:
                self.process.stdin.close()
            try:
                self.process.wait(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
            if self.process.stdout:
                self.process.stdout.close()
            self.process = None
        self.hello = None
