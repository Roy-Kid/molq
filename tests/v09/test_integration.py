"""Real execution and peer transports, rather than implementation-shaped mocks."""

import asyncio
import base64
import json
import os
import subprocess
import sys
import time

import pytest
from aiohttp import ClientSession
from aiohttp.test_utils import TestServer

from molq import (
    AsyncMolq,
    Execution,
    ExecutionUnit,
    JobSpec,
    Molq,
    Parallel,
    Sequence,
    UnitRef,
)
from molq.client.wire import Wire
from molq.errors import MolqError
from molq.runtime import Runtime
from molq.runtime.rpc import decode, dispatch
from molq.runtime.server import application
from molq.transport import LocalTransport, SshTransport


@pytest.mark.skipif(
    os.name == "nt",
    reason="Local Shell execution needs a POSIX Bash target; Windows control-plane tests run separately",
)
def test_real_parallel_plan_barrier_sequence_and_output(tmp_path):
    code = 'import pathlib,time,sys; p=pathlib.Path(sys.argv[1]); p.touch(); other=pathlib.Path(sys.argv[2]); deadline=time.monotonic()+5\nwhile not other.exists():\n if time.monotonic()>deadline: sys.exit(7)\n time.sleep(.01)\nprint("parallel")'
    with Molq(registry=tmp_path / "registry.db") as mq:
        target = mq.clusters.register(
            name="local", scheduler="shell", target_root=str(tmp_path / "target")
        )

        def unit(id, argv):
            return ExecutionUnit.argv(id, argv)

        a, b = tmp_path / "a", tmp_path / "b"
        spec = JobSpec(
            Execution(
                (
                    unit("prepare", [sys.executable, "-c", 'print("prepare")']),
                    unit("a", [sys.executable, "-c", code, str(a), str(b)]),
                    unit("b", [sys.executable, "-c", code, str(b), str(a)]),
                    unit("report", [sys.executable, "-c", 'print("report")']),
                ),
                Sequence(
                    (
                        UnitRef("prepare"),
                        Parallel((UnitRef("a"), UnitRef("b"))),
                        UnitRef("report"),
                    )
                ),
            )
        )
        job = target.submit(spec)
        result = job.wait(timeout=10, interval=0.02)
        assert result["completion"]["successful"]
        lines = job.logs()["text"].splitlines()
        assert (
            lines[0] == "prepare"
            and lines[-1] == "report"
            and lines.count("parallel") == 2
        )


@pytest.mark.skipif(os.name == "nt", reason="Requires local Bash")
def test_sequence_failure_stops_later_units_and_wait_has_no_client_state_machine(
    tmp_path,
):
    later = tmp_path / "must-not-exist"
    with Molq(registry=tmp_path / "registry.db") as mq:
        target = mq.clusters.register(
            name="local", scheduler="shell", target_root=str(tmp_path / "target")
        )
        units = (
            ExecutionUnit.argv("fail", [sys.executable, "-c", "raise SystemExit(23)"]),
            ExecutionUnit.argv(
                "later",
                [
                    sys.executable,
                    "-c",
                    f"from pathlib import Path; Path({str(later)!r}).touch()",
                ],
            ),
        )
        job = target.submit(
            JobSpec(Execution(units, Sequence((UnitRef("fail"), UnitRef("later")))))
        )
        result = job.wait(timeout=5, interval=0.02)
        assert result["completion"]["successful"] is False
        assert result["snapshots"][0]["exit_code"] == 23
        assert not later.exists()


@pytest.mark.skipif(os.name == "nt", reason="Requires local Bash/process groups")
def test_cancel_real_process_group_and_client_close_does_not_cancel(tmp_path):
    started = time.monotonic()
    with Molq(registry=tmp_path / "registry.db") as mq:
        target = mq.clusters.register(
            name="local", scheduler="shell", target_root=str(tmp_path / "target")
        )
        job = target.submit(argv=[sys.executable, "-c", "import time; time.sleep(30)"])
        ref = job.ref
    assert time.monotonic() - started < 5
    with Molq(registry=tmp_path / "registry.db") as mq:
        job = mq.job(ref)
        assert job.status()["snapshots"][0]["state"] == "running"
        assert job.cancel()["outcome"] == "accepted"
        assert (
            job.wait(timeout=5, interval=0.02)["snapshots"][0]["state"] == "cancelled"
        )
        assert job.cancel()["outcome"] == "already_terminal"


def test_async_stdio_python_projection(tmp_path):
    async def scenario():
        async with AsyncMolq(registry=tmp_path / "registry.db") as mq:
            await mq.clusters.register(
                name="local", scheduler="shell", target_root=str(tmp_path / "target")
            )
            info = await mq.cluster("local").definition()
            assert info["name"] == "local"
            assert len(await mq.clusters.list()) == 1
            if os.name != "nt":
                job = await mq.cluster("local").submit(
                    argv=[sys.executable, "-c", 'print("async")']
                )
                result = await job.wait(timeout=5, interval=0.02)
                assert result["completion"]["successful"]
                assert "async" in (await job.logs())["text"]

    asyncio.run(scenario())


def test_http_ws_auth_same_runtime_and_generated_web_client(tmp_path):
    async def scenario():
        runtime = Runtime(tmp_path / "registry.db")
        token = "test-secret-at-least-16"
        server = TestServer(application(runtime, token))
        await server.start_server()
        endpoint = str(server.make_url("/")).rstrip("/")
        try:
            async with ClientSession() as session:
                async with session.post(
                    endpoint + "/rpc",
                    json={"jsonrpc": "2.0", "id": 1, "method": "molq.hello"},
                ) as response:
                    assert response.status == 401
                    assert (await response.json())["error"]["data"][
                        "kind"
                    ] == "AUTH_REQUIRED"
                async with session.post(
                    endpoint + "/rpc",
                    headers={
                        "Authorization": "Bearer " + token,
                        "Origin": "http://evil.test",
                    },
                    json={},
                ) as response:
                    assert response.status == 403
                async with session.get(endpoint + "/") as response:
                    assert response.status == 200 and "molq" in await response.text()
                for path in ("app.js", "wire.js", "style.css"):
                    async with session.get(endpoint + "/" + path) as response:
                        assert response.status == 200
                async with session.get(endpoint + "/secret") as response:
                    assert response.status == 404
                with pytest.raises(MolqError) as error:
                    async with AsyncMolq(
                        endpoint=endpoint, token="wrong-token"
                    ) as denied:
                        await denied.rpc("clusters.list")
                assert error.value.kind == "AUTH_REQUIRED"
                async with AsyncMolq(endpoint=endpoint, token=token) as mq:
                    hello = await mq.rpc("molq.hello")
                    assert hello["runtime_instance_id"] == runtime.id
                    await mq.clusters.register(
                        name="local",
                        scheduler="shell",
                        target_root=str(tmp_path / "target"),
                    )
                    assert len(await mq.clusters.list()) == 1
                    with pytest.raises(MolqError) as e:
                        await mq.rpc("events.subscribe")
                    assert e.value.kind == "RPC_CHANNEL_UNSUPPORTED"
                    ws = await session.ws_connect(endpoint + "/ws")
                    await ws.send_json({"token": token})
                    await ws.send_json(
                        {
                            "jsonrpc": "2.0",
                            "id": 7,
                            "method": "molq.hello",
                            "params": {},
                        }
                    )
                    response = await ws.receive_json()
                    assert (
                        response["result"]["runtime_instance_id"]
                        == hello["runtime_instance_id"]
                    )
                    await ws.send_json(
                        {
                            "jsonrpc": "2.0",
                            "id": 8,
                            "method": "events.subscribe",
                            "params": {},
                        }
                    )
                    events = await ws.receive_json()
                    assert events["result"]["resync"]
                    await ws.close()
                    bad = await session.ws_connect(endpoint + "/ws")
                    await bad.send_json({"token": "bad"})
                    assert (await bad.receive_json())["error"]["data"][
                        "kind"
                    ] == "AUTH_REQUIRED"
                    await bad.close()
        finally:
            await server.close()

    asyncio.run(scenario())


def test_files_are_chunked_and_scoped_to_target(tmp_path):
    async def scenario():
        runtime = Runtime(tmp_path / "registry.db")
        try:
            await runtime.call(
                "clusters.register",
                {
                    "name": "local",
                    "scheduler": "shell",
                    "target_root": str(tmp_path / "target"),
                },
            )
            text = base64.b64encode(b"hello-world").decode()
            await runtime.call(
                "files.write", {"cluster": "local", "path": "input", "data": text}
            )
            result = await runtime.call(
                "files.read",
                {"cluster": "local", "path": "input", "offset": 6, "limit": 5},
            )
            assert base64.b64decode(result["data"]) == b"world"
            copied = await runtime.call(
                "files.transfer",
                {
                    "source_cluster": "local",
                    "source_path": "input",
                    "destination_cluster": "local",
                    "destination_path": "copy",
                },
            )
            assert copied["bytes"] == 11
            for path in ("../../escape", str(tmp_path / "outside")):
                with pytest.raises(MolqError):
                    await runtime.call("files.read", {"cluster": "local", "path": path})
            if os.name != "nt":
                (tmp_path / "outside").write_text("no")
                (tmp_path / "target/link").symlink_to(tmp_path / "outside")
                with pytest.raises(MolqError):
                    await runtime.call(
                        "files.read", {"cluster": "local", "path": "link"}
                    )
            with pytest.raises(MolqError):
                await runtime.call(
                    "files.write",
                    {"cluster": "local", "path": "input", "data": "%%%bad"},
                )
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_rpc_notifications_batches_schema_and_frames(tmp_path):
    async def scenario():
        runtime = Runtime(tmp_path / "registry.db")
        try:
            invalid = await dispatch(
                runtime, {"jsonrpc": "wrong", "id": 1, "method": "molq.hello"}
            )
            assert invalid["error"]["code"] == -32600
            assert (await dispatch(runtime, []))["error"]["code"] == -32600
            assert (
                await dispatch(
                    runtime,
                    {"jsonrpc": "2.0", "method": "clusters.register", "params": {}},
                )
                is None
            )
            assert not runtime.registry.list()
            batch = await dispatch(
                runtime,
                [
                    {"jsonrpc": "2.0", "id": 1, "method": "molq.hello"},
                    {"jsonrpc": "2.0", "id": 2, "method": "missing"},
                ],
            )
            assert (
                batch[0]["result"]["release"] == "0.9.0"
                and batch[1]["error"]["code"] == -32601
            )
            invalid = await dispatch(
                runtime,
                {"jsonrpc": "2.0", "id": 3, "method": "jobs.submit", "params": []},
            )
            assert invalid["error"]["code"] == -32602
        finally:
            await runtime.close()

    asyncio.run(scenario())
    for frame in (b"{", b"NaN", b"x" * 1048577):
        with pytest.raises(MolqError):
            decode(frame)


def test_transport_timeout_output_bound_and_quote_roundtrip(tmp_path):
    async def scenario():
        transport = LocalTransport()
        result = await transport.run(
            [
                sys.executable,
                "-c",
                "import sys; print(sys.argv[1])",
                "$(should-not-run) a b;`no`",
            ]
        )
        assert result.text.strip() == "$(should-not-run) a b;`no`"
        with pytest.raises(MolqError):
            await transport.run(["molq-nonexistent-program-09"])
        with pytest.raises(MolqError):
            await transport.run(
                [sys.executable, "-c", "import time;time.sleep(30)"], timeout=0.02
            )
        with pytest.raises(MolqError):
            await transport.run([sys.executable, "-c", 'print("x"*1100000)'])
        path = tmp_path / "file"
        await transport.write(str(path), b"hello")
        await transport.write(str(path), b"X", offset=1)
        assert await transport.read(str(path)) == b"hXllo"
        with pytest.raises(MolqError):
            await transport.read(str(tmp_path / "missing"))

    asyncio.run(scenario())


def test_ssh_defers_configuration_and_mux_to_openssh():
    from conftest import FakeTransport

    async def scenario():
        ssh = SshTransport("hpc")
        fake = FakeTransport(["ok"])
        ssh.local = fake
        await ssh.run(["echo", "a b;$(bad)"], timeout=17)
        argv, timeout, _ = fake.calls[0]
        assert argv == [
            "ssh",
            "-T",
            "-o",
            "BatchMode=yes",
            "--",
            "hpc",
            "echo 'a b;$(bad)'",
        ]
        assert timeout == 17
        assert not any(
            "ControlMaster" in part
            or "ControlPath" in part
            or "ProxyJump" in part
            or "IdentityFile" in part
            for part in argv
        )

    asyncio.run(scenario())


def test_cli_installed_path_json_and_exit_semantics(tmp_path):
    def cli(*argv):
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "molq",
                "--registry",
                str(tmp_path / "registry.db"),
                *argv,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )

    result = cli(
        "clusters",
        "register",
        "--definition",
        json.dumps(
            {
                "name": "local",
                "scheduler": "shell",
                "target_root": str(tmp_path / "target"),
            }
        ),
    )
    assert result.returncode == 0, json.loads(result.stdout)
    assert cli("clusters", "list").returncode == 0
    assert cli("discover").returncode == 0
    assert cli("invalid-command").returncode == 2
    assert cli("rpc", "clusters.get", "--params", "{bad").returncode == 2
    if os.name == "nt":
        return
    job = cli("submit", "local", "--", sys.executable, "-c", "raise SystemExit(17)")
    assert job.returncode == 0, job.stdout
    ref = json.loads(job.stdout)["result"]["ref"]
    result = cli(
        "wait", "--ref", json.dumps(ref), "--timeout", "5", "--interval", ".02"
    )
    assert result.returncode == 9, result.stdout
    assert json.loads(result.stdout)["result"]["completion"]["successful"] is False


def test_sync_wire_http_errors_are_structured(tmp_path):
    class Response:
        def __init__(self, data):
            self.data = data

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, size):
            return self.data

    from unittest.mock import patch

    wire = Wire(endpoint="https://localhost.invalid", token="token")
    response = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"version": {"major": 1}, "registry_id": "r"},
        }
    ).encode()
    with patch("urllib.request.urlopen", return_value=Response(response)):
        assert wire.connect()["registry_id"] == "r"
    wire.close()


def test_observer_routes_runtime_events_and_notification_failure_is_fail_open(
    tmp_path, monkeypatch, capsys
):
    from aiohttp import web

    from molq import observer

    event = {"ref": {"native_id": "1"}, "state": "succeeded", "terminal": True}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def connect(self):
            return {}

        async def close(self):
            pass

        async def call(self, method, params=None):
            assert method == "jobs.observe"
            return {"cursor": "opaque", "changes": [event]}

    monkeypatch.setattr(observer, "AsyncWire", FakeClient)

    async def scenario():
        app = web.Application()

        async def failed(request):
            assert await request.json() == event
            raise web.HTTPInternalServerError()

        app.router.add_post("/ingest", failed)
        server = TestServer(app)
        await server.start_server()
        try:
            await observer.run(
                clusters=["cluster"],
                once=True,
                nerve_endpoint=str(server.make_url("/ingest")),
            )
        finally:
            await server.close()

    asyncio.run(scenario())
    assert json.loads(capsys.readouterr().out)["params"] == event
    with pytest.raises(MolqError):
        asyncio.run(observer.run(interval=0, once=True))


def test_architecture_peer_clients_have_no_runtime_imports():
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "src/molq"
    for path in [
        *(root / "client").glob("*.py"),
        root / "observer.py",
        root / "domain.py",
    ]:
        tree = ast.parse(path.read_text())
        imports = [
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        ]
        assert not any(
            name.startswith(
                ("molq.runtime", "molq.registry", "molq.scheduler", "molq.transport")
            )
            for name in imports
        ), path
    assert (
        not (root / "submitor.py").exists()
        and not (root / "store/jobstore.py").exists()
    )


def test_cli_and_observer_do_not_wrap_sdk_facades():
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "src/molq"
    for path in (root / "cli/main.py", root / "observer.py"):
        modules = [
            n.module
            for n in ast.walk(ast.parse(path.read_text()))
            if isinstance(n, ast.ImportFrom)
        ]
        assert "molq.client.objects" not in modules
        assert "molq.client.async_objects" not in modules


def test_wire_pre_dispatch_error_uses_shared_kind():
    from io import BytesIO
    from unittest.mock import patch

    from molq.runtime.rpc import error_response

    response = BytesIO(
        json.dumps(error_response(None, MolqError("AUTH_REQUIRED", "Denied"))).encode()
    )
    wire = Wire(endpoint="http://localhost.invalid")
    with patch("urllib.request.urlopen", return_value=response):
        with pytest.raises(MolqError) as error:
            wire.connect()
    assert error.value.kind == "AUTH_REQUIRED"
