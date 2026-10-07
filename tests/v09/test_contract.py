"""Breaking-release contracts, including the real no-service path."""

import json
import subprocess
import sys

import pytest

from molq import Execution, ExecutionUnit, JobSpec, Molq, MolqError, Resources


def test_no_service_submit_wait_restart_and_no_job_tables(tmp_path):
    registry = tmp_path / "registry.db"
    with Molq(registry=registry) as mq:
        mq.clusters.register(
            name="local", scheduler="shell", target_root=str(tmp_path / "target")
        )
        job = mq.cluster("local").submit(argv=[sys.executable, "-c", 'print("molq09")'])
        ref = job.ref
    with Molq(registry=registry) as mq:
        result = mq.job(ref).wait(timeout=10, interval=0.05)
        assert result["completion"]["all_confirmed_terminal"]
        assert result["snapshots"][0]["state"] == "succeeded"
        assert "molq09" in mq.job(ref).logs()["text"]
    import sqlite3

    with sqlite3.connect(registry) as db:
        tables = {
            r[0]
            for r in db.execute("select name from sqlite_master where type='table'")
        }
    assert tables == {"schema_meta", "clusters", "settings", "presets"}


def test_unknown_cluster_is_not_local(tmp_path):
    with Molq(registry=tmp_path / "registry.db") as mq:
        with pytest.raises(MolqError) as e:
            mq.cluster("missing").submit(argv=["true"])
        assert e.value.kind == "CLUSTER_NOT_FOUND"


def test_single_job_and_multi_unit_schema_are_orthogonal():
    spec = JobSpec(
        execution=Execution(units=(ExecutionUnit.argv("main", ["echo", "ok"]),)),
        resources=Resources(nodes=2, tasks=4),
    )
    wire = spec.to_wire()
    assert wire["resources"]["nodes"] == 2
    assert wire["execution"]["units"][0]["command"]["argv"] == ["echo", "ok"]
    assert "scheduler" not in wire


def test_client_import_has_no_runtime_side_effects(tmp_path):
    code = 'import molq, sys; assert not any(x.startswith("molq.runtime") or x.startswith("molq.scheduler") or x.startswith("molq.registry") for x in sys.modules)'
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr


def test_cli_is_structured_on_input_error():
    proc = subprocess.run(
        [sys.executable, "-m", "molq", "rpc", "not.a.method"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode != 0
    assert json.loads(proc.stdout)["error"]["data"]["kind"] == "METHOD_NOT_FOUND"
