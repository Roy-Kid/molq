"""Registry ownership, live truth, bounded cache and observation recovery."""

import asyncio
import copy
import sqlite3

import pytest

from molq.errors import MolqError
from molq.runtime.observation import Observation, collection, snapshot
from molq.runtime.planning import normalize
from molq.scheduler.base import NativeJob


def run(value):
    return asyncio.run(value)


def register(runtime, tmp_path, name="one"):
    return run(
        runtime.call(
            "clusters.register",
            {"name": name, "scheduler": "shell", "target_root": str(tmp_path / name)},
        )
    )


@pytest.mark.parametrize(
    "field",
    [
        "monitor_preferences",
        "interval",
        "supports_gpu",
        "capabilities",
        "notification_preferences",
        "observation_cadence",
    ],
)
def test_cluster_has_no_monitor_or_capability_state(runtime, tmp_path, field):
    with pytest.raises(MolqError) as e:
        run(
            runtime.call(
                "clusters.register",
                {
                    "name": "bad",
                    "scheduler": "shell",
                    "target_root": str(tmp_path),
                    "transport": {"kind": "local"},
                    field: True,
                },
            )
        )
    assert e.value.kind == "INVALID_INPUT"
    assert not runtime.registry.list()


def test_registry_rename_revision_and_destination_change(runtime, tmp_path):
    record = register(runtime, tmp_path)
    definition = {k: v for k, v in record.items() if k not in {"id", "revision"}}
    definition["name"] = "renamed"
    updated = run(
        runtime.call(
            "clusters.update",
            {"cluster": record["id"], "definition": definition, "expected_revision": 1},
        )
    )
    assert updated["id"] == record["id"] and updated["revision"] == 2
    with pytest.raises(MolqError, match="revision"):
        run(
            runtime.call(
                "clusters.remove", {"cluster": record["id"], "expected_revision": 1}
            )
        )
    definition["scheduler"] = "slurm"
    with pytest.raises(MolqError, match="new Cluster ID"):
        run(
            runtime.call(
                "clusters.update",
                {
                    "cluster": record["id"],
                    "definition": definition,
                    "expected_revision": 2,
                },
            )
        )
    run(runtime.call("clusters.remove", {"cluster": "renamed", "expected_revision": 2}))
    assert not runtime.registry.list()


def test_owned_state_namespaces_only(runtime, tmp_path):
    assert (
        run(runtime.call("config.set", {"key": "cache_max_entries", "value": 16}))[
            "value"
        ]
        == 16
    )
    assert runtime.observation.max_entries == 16
    assert run(runtime.call("config.get", {"key": "cache_max_entries"}))["value"] == 16
    with pytest.raises(MolqError):
        run(runtime.call("config.set", {"key": "job_history", "value": []}))
    with pytest.raises(MolqError):
        run(runtime.call("config.set", {"key": "cache_max_entries", "value": -1}))
    run(
        runtime.call(
            "presets.set", {"key": "small", "value": {"resources": {"tasks": 2}}}
        )
    )
    assert (
        run(runtime.call("presets.get", {"key": "small"}))["value"]["resources"][
            "tasks"
        ]
        == 2
    )
    assert len(run(runtime.call("presets.list", {}))) == 1
    tables = {
        row[0]
        for row in runtime.registry.db.execute(
            "select name from sqlite_master where type='table'"
        )
    }
    assert tables == {"schema_meta", "clusters", "settings", "presets"}


@pytest.mark.parametrize(
    "mutation",
    [
        lambda e: e["units"].append(copy.deepcopy(e["units"][0])),
        lambda e: e.update(plan={"kind": "unit", "ref": "missing"}),
        lambda e: e.update(
            plan={
                "kind": "parallel",
                "children": [
                    {"kind": "unit", "ref": "main"},
                    {"kind": "unit", "ref": "main"},
                ],
            }
        ),
        lambda e: e["units"][0].update(launch={"kind": "mpi"}),
    ],
)
def test_invalid_execution_topology_rejected(spec, mutation):
    mutation(spec["execution"])
    with pytest.raises(MolqError):
        normalize(spec, {})


def test_default_merge_is_once_and_spec_not_mutated(spec):
    before = copy.deepcopy(spec)
    normalized = normalize(spec, {"resources": {"tasks": 2}, "env": {"A": "default"}})
    assert normalized["resources"]["tasks"] == 2
    assert normalized["execution"]["env"] == {"A": "default"}
    assert spec == before


def test_resource_budget_rejects_parallel_oversubscription(spec):
    spec["resources"] = {"tasks": 1}
    spec["execution"]["units"].append(
        {"id": "two", "command": {"kind": "argv", "argv": ["true"]}}
    )
    spec["execution"]["plan"] = {
        "kind": "parallel",
        "children": [{"kind": "unit", "ref": "main"}, {"kind": "unit", "ref": "two"}],
    }
    with pytest.raises(MolqError) as e:
        normalize(spec, {})
    assert e.value.kind == "EXECUTION_RESOURCE_CONFLICT"


class FakeScheduler:
    def __init__(self):
        self.state = "running"
        self.fail = False
        self.incarnation = "start"
        self.query_calls = 0
        self.cancel_calls = 0

    async def query_many(self, ids):
        self.query_calls += 1
        if self.fail:
            raise MolqError("SCHEDULER_UNAVAILABLE", "Network down")
        return {i: NativeJob(i, self.incarnation, self.state, "queue") for i in ids}

    async def history(self, ids):
        return await self.query_many(ids)

    async def list(self):
        return list((await self.query_many(["123"])).values())

    async def cancel(self, job):
        self.cancel_calls += 1
        return {"outcome": "accepted"}


def fake_scope(runtime, tmp_path):
    cluster = register(runtime, tmp_path)
    fake = FakeScheduler()
    runtime.schedulers[cluster["id"]] = fake
    runtime.locks[cluster["id"]] = asyncio.Lock()
    ref = {
        "registry_id": runtime.registry.id,
        "cluster_id": cluster["id"],
        "native_id": "123",
        "incarnation": "start",
    }
    return cluster, fake, ref


def test_network_failure_never_becomes_lost_or_terminal(runtime, tmp_path):
    _, fake, ref = fake_scope(runtime, tmp_path)
    live = run(runtime.call("jobs.get", {"ref": ref}))
    assert not live["completion"]["all_confirmed_terminal"]
    fake.fail = True
    result = run(runtime.call("jobs.get_many", {"refs": [ref]}))
    assert not result["coverage"]["complete"]
    assert not result["snapshots"][0]["terminal"]
    assert result["snapshots"][0]["last_known"]["state"] == "running"
    assert result["snapshots"][0]["freshness"]["status"] == "unavailable"
    assert not result["completion"]["all_confirmed_terminal"]


def test_cache_freshness_live_requeries_terminal(runtime, tmp_path):
    _, fake, ref = fake_scope(runtime, tmp_path)
    fake.state = "succeeded"
    run(runtime.call("jobs.get", {"ref": ref}))
    before = fake.query_calls
    cached = run(
        runtime.call("jobs.get", {"ref": ref, "consistency": "bounded", "max_age": 30})
    )
    assert (
        fake.query_calls == before
        and cached["snapshots"][0]["freshness"]["status"] == "cached"
    )
    run(runtime.call("jobs.get", {"ref": ref, "consistency": "live"}))
    assert fake.query_calls == before + 1
    runtime.observation.cache.clear()
    with pytest.raises(MolqError) as e:
        run(runtime.call("jobs.get", {"ref": ref, "consistency": "cached"}))
    assert e.value.kind == "CACHE_MISS"


def test_reused_id_cannot_be_cancelled(runtime, tmp_path):
    _, fake, ref = fake_scope(runtime, tmp_path)
    fake.incarnation = "new-allocation"
    with pytest.raises(MolqError) as e:
        run(runtime.call("jobs.cancel", {"ref": ref}))
    assert e.value.kind == "JOB_IDENTITY_MISMATCH" and fake.cancel_calls == 0
    ref["registry_id"] = "foreign"
    with pytest.raises(MolqError) as e:
        run(runtime.call("jobs.get", {"ref": ref}))
    assert e.value.kind == "REGISTRY_MISMATCH"


def test_observe_diff_and_resync_are_runtime_owned(runtime, tmp_path):
    cluster, fake, ref = fake_scope(runtime, tmp_path)
    first = run(runtime.call("jobs.observe", {"refs": [ref]}))
    assert first["resync"] and not first["changes"]
    fake.state = "succeeded"
    second = run(
        runtime.call("jobs.observe", {"refs": [ref], "cursor": first["cursor"]})
    )
    assert second["changes"][0]["terminal"]
    assert second["completion"]["all_confirmed_terminal"]
    event_cursor = run(runtime.call("events.subscribe", {}))["cursor"]
    assert not run(runtime.call("events.subscribe", {"cursor": event_cursor}))["resync"]
    runtime.observation.clear()
    resync = run(
        runtime.call("jobs.observe", {"refs": [ref], "cursor": second["cursor"]})
    )
    assert resync["resync"] and not resync["changes"]
    assert run(runtime.call("events.subscribe", {"cursor": event_cursor}))["resync"]


def test_partial_sample_does_not_emit_false_completion(runtime, tmp_path):
    _, fake, ref = fake_scope(runtime, tmp_path)
    first = run(runtime.call("jobs.observe", {"refs": [ref]}))
    fake.fail = True
    partial = run(
        runtime.call("jobs.observe", {"refs": [ref], "cursor": first["cursor"]})
    )
    assert (
        not partial["changes"] and not partial["completion"]["all_confirmed_terminal"]
    )


def test_baselines_and_cache_bounded_and_cursor_scope_isolated():
    observation = Observation(max_entries=2)
    for i in range(100):
        ref = {
            "registry_id": "r",
            "cluster_id": "c",
            "native_id": str(i),
            "incarnation": "s",
        }
        value = snapshot(ref, NativeJob(str(i), "s", "running", "queue"))
        observation.remember(value)
        observation.observe(collection([value]), str(i), None)
    assert len(observation.cache) == 2 and len(observation.baselines) == 64
    assert observation.since("malformed")["resync"]


def test_registry_defends_short_overlap(tmp_path):
    from molq.registry import Registry

    first = Registry(tmp_path / "registry.db")
    second = Registry(tmp_path / "registry.db")
    try:
        assert first.id == second.id
        first.db.execute("BEGIN IMMEDIATE")
        with pytest.raises(MolqError) as e:
            second.mutate({"name": "x", "scheduler": "shell", "target_root": "/tmp"})
        assert e.value.kind == "STATE_BUSY"
        first.db.execute("ROLLBACK")
    finally:
        first.close()
        second.close()


def test_incompatible_owned_schema_fails_without_job_migration(tmp_path):
    from molq.registry import Registry

    path = tmp_path / "registry.db"
    registry = Registry(path)
    registry.close()
    with sqlite3.connect(path) as db:
        db.execute("update schema_meta set value='99' where key='schema_version'")
    with pytest.raises(MolqError) as e:
        Registry(path)
    assert e.value.kind == "STATE_SCHEMA_INCOMPATIBLE"


def test_generated_wire_dtos_match_protocol_names():
    from molq.protocol import contract, types

    for name in contract()["$defs"]:
        assert hasattr(types, name)


def test_identical_live_batches_share_one_inflight_native_query(runtime, tmp_path):
    _, fake, ref = fake_scope(runtime, tmp_path)
    original = fake.query_many

    async def delayed(ids):
        await asyncio.sleep(0.02)
        return await original(ids)

    fake.query_many = delayed

    async def scenario():
        a, b = await asyncio.gather(
            runtime.call("jobs.get", {"ref": ref}),
            runtime.call("jobs.get", {"ref": ref}),
        )
        assert a["snapshots"][0]["state"] == b["snapshots"][0]["state"]
        assert fake.query_calls == 1
        await runtime.call("jobs.get", {"ref": ref})
        assert fake.query_calls == 2

    run(scenario())


def test_submit_request_key_deduplicates_only_this_runtime(runtime, tmp_path, spec):
    import os

    if os.name == "nt":
        pytest.skip("Local Shell target needs Bash")
    cluster = register(runtime, tmp_path)

    async def scenario():
        params = {
            "cluster": cluster["id"],
            "spec": spec,
            "request_key": "one-operation",
        }
        a, b = await asyncio.gather(
            runtime.call("jobs.submit", params), runtime.call("jobs.submit", params)
        )
        assert a["ref"] == b["ref"]
        with pytest.raises(MolqError):
            await runtime.call(
                "jobs.submit",
                {
                    **params,
                    "spec": {
                        "execution": {
                            "units": [
                                {
                                    "id": "main",
                                    "command": {
                                        "kind": "argv",
                                        "argv": ["echo", "different"],
                                    },
                                }
                            ]
                        }
                    },
                },
            )

    run(scenario())


def test_preview_validate_and_public_result_schema(runtime, tmp_path, spec):
    from molq.protocol import validate

    cluster = register(runtime, tmp_path)
    validated = run(
        runtime.call("jobs.validate", {"cluster": cluster["id"], "spec": spec})
    )
    preview = run(
        runtime.call("jobs.preview", {"cluster": cluster["id"], "spec": spec})
    )
    assert validated["spec"] == preview["spec"] and "launch.tmp" in preview["script"]
    validate(cluster, {"$ref": "#/$defs/ClusterRecord"})
    ref = {"registry_id": "r", "cluster_id": "c", "native_id": "1", "incarnation": "s"}
    validate(
        collection(
            [snapshot(ref, NativeJob("1", "s", "succeeded", "accounting", exit_code=0))]
        ),
        {"$ref": "#/$defs/ObservationResult"},
    )


def test_legacy_or_future_database_is_rejected_without_schema_changes(tmp_path):
    import sqlite3

    from molq.registry import Registry

    for legacy in (True, False):
        path = tmp_path / ("legacy.db" if legacy else "future.db")
        with sqlite3.connect(path) as db:
            if legacy:
                db.execute("CREATE TABLE jobs (id TEXT)")
            else:
                db.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY,value TEXT)")
                db.execute("INSERT INTO schema_meta VALUES ('schema_version','99')")
            before = list(
                db.execute("SELECT name,sql FROM sqlite_master ORDER BY name")
            )
        with pytest.raises(MolqError) as error:
            Registry(path)
        assert error.value.kind == "STATE_SCHEMA_INCOMPATIBLE"
        with sqlite3.connect(path) as db:
            assert (
                list(db.execute("SELECT name,sql FROM sqlite_master ORDER BY name"))
                == before
            )


def test_empty_argv_arguments_and_mpi_placement_conflict():
    from molq.runtime.planning import normalize

    request = {
        "execution": {
            "units": [{"id": "main", "command": {"kind": "argv", "argv": ["echo", ""]}}]
        }
    }
    assert normalize(request, {})["execution"]["units"][0]["command"]["argv"][-1] == ""
    request["execution"]["units"][0]["command"]["argv"] = [""]
    with pytest.raises(MolqError):
        normalize(request, {})


def test_observation_byte_limits_force_honest_cursor_resync():
    from molq.runtime.observation import Observation, collection, snapshot
    from molq.scheduler.base import NativeJob

    observation = Observation(max_bytes=4096)
    values = []
    for number in range(2):
        ref = {
            "registry_id": "r",
            "cluster_id": "c",
            "native_id": str(number),
            "incarnation": "t",
        }
        value = snapshot(
            ref, NativeJob(str(number), "t", "running", "queue", "x" * 3000)
        )
        values.append(value)
        observation.remember(value)
    assert len(observation.cache) == 1 and observation.cache_bytes <= 4096
    first = observation.observe(collection(values), "scope", None)
    second = observation.observe(collection(values), "scope", first["cursor"])
    assert second["resync"] and not second["changes"]
    assert observation.baseline_bytes <= 4096
