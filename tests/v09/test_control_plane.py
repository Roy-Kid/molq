"""Portable control plane tests; target POSIX paths need no local Bash."""

import asyncio
import json
import sys

import pytest

from molq import AsyncMolq, Molq, MolqError


def test_native_peer_registry_and_revision_rpc(tmp_path):
    registry = tmp_path / "registry.db"
    with Molq(registry=registry) as mq:
        cluster = mq.clusters.register(
            name="remote",
            scheduler="slurm",
            transport={"kind": "ssh", "alias": "hpc"},
            target_root="/scratch/molq",
        )
        definition = cluster.definition()
        assert definition["transport"] == {"kind": "ssh", "alias": "hpc"}
        with pytest.raises(MolqError) as error:
            mq.rpc(
                "clusters.register",
                name="bad",
                scheduler="slurm",
                target_root="/scratch",
                capability={},
            )
        assert error.value.kind == "INVALID_INPUT"
    with Molq(registry=registry) as mq:
        assert mq.cluster("remote").definition()["id"] == definition["id"]


def test_async_native_peer_without_local_scheduler(tmp_path):
    async def scenario():
        async with AsyncMolq(registry=tmp_path / "registry.db") as mq:
            await mq.clusters.register(
                name="remote",
                scheduler="pbs",
                transport={"kind": "ssh", "alias": "hpc"},
                target_root="/scratch",
                pbs_dialect="openpbs",
            )
            assert len(await mq.clusters.list()) == 1

    asyncio.run(scenario())


def test_stdio_subscription_pushes_registry_reset(tmp_path):
    async def scenario():
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "molq",
            "runtime",
            "rpc",
            "--stdio",
            "--registry",
            str(tmp_path / "registry.db"),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )

        async def call(identity, method, params):
            process.stdin.write(
                (
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": identity,
                            "method": method,
                            "params": params,
                        }
                    )
                    + "\n"
                ).encode()
            )
            await process.stdin.drain()
            return json.loads(await asyncio.wait_for(process.stdout.readline(), 5))

        try:
            assert (await call(1, "events.subscribe", {}))["result"]["resync"]
            assert (
                await call(
                    2,
                    "clusters.register",
                    {
                        "name": "remote",
                        "scheduler": "slurm",
                        "target_root": "/scratch",
                        "transport": {"kind": "ssh", "alias": "hpc"},
                    },
                )
            )["result"]["id"]
            pushed = json.loads(await asyncio.wait_for(process.stdout.readline(), 5))
            assert pushed["method"] == "events" and pushed["params"]["resync"]
        finally:
            process.stdin.close()
            await asyncio.wait_for(process.wait(), 10)

    asyncio.run(scenario())


def test_native_startup_schema_error_retains_kind(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE jobs (id TEXT)")
    with pytest.raises(MolqError) as error:
        with Molq(registry=path):
            pass
    assert error.value.kind == "STATE_SCHEMA_INCOMPATIBLE"


def test_cli_submit_spec_options_after_destination():
    from molq.cli.main import parser

    parsed = parser().parse_args(["submit", "hpc", "--spec", "@spec.json"])
    assert parsed.spec == "@spec.json" and not parsed.argv
