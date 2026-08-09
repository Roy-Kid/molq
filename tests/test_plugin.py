"""Tests for the molq plugin host and official nerve plugin mapping."""

from __future__ import annotations

from pathlib import Path

import pytest

from molq.callbacks import EventBus, EventPayload, EventType
from molq.config import MolqConfig, enabled_plugin_names, load_config
from molq.models import JobRecord
from molq.plugin import (
    BUILTIN_PLUGIN_FACTORIES,
    PluginContext,
    PluginManager,
    available_plugins,
    create_plugin,
)
from molq.plugins.nerve.mapping import build_snapshots, facets_for_state
from molq.status import JobState


def _record(
    job_id: str,
    state: JobState,
    *,
    cluster: str = "dev",
    metadata: dict | None = None,
) -> JobRecord:
    return JobRecord(
        job_id=job_id,
        cluster_name=cluster,
        scheduler="local",
        state=state,
        command_display=f"cmd-{job_id}",
        metadata=metadata or {},
    )


class TestPluginDiscovery:
    def test_nerve_is_builtin(self):
        assert "nerve" in BUILTIN_PLUGIN_FACTORIES
        assert "nerve" in available_plugins()

    def test_create_nerve_plugin(self):
        p = create_plugin("nerve")
        assert p.name == "nerve"

    def test_unknown_plugin_raises(self):
        with pytest.raises(KeyError):
            create_plugin("does-not-exist-xyz")


class TestPluginManager:
    def test_load_and_detach(self):
        bus = EventBus()
        mgr = PluginManager()
        records: dict[str, JobRecord] = {}

        def ctx_factory(name, pcfg):
            return PluginContext(
                event_bus=bus,
                cluster_name="dev",
                config=pcfg,
                get_record=lambda jid: records.get(jid),
                list_active_records=lambda: [
                    r for r in records.values() if not r.state.is_terminal
                ],
                list_records=lambda: list(records.values()),
            )

        names = mgr.load(["nerve"], ctx_factory=ctx_factory, configs={})
        assert names == ["nerve"]
        assert len(mgr.attached) == 1
        mgr.detach_all()
        assert mgr.attached == ()

    def test_disabled_skipped(self):
        bus = EventBus()
        mgr = PluginManager()

        def ctx_factory(name, pcfg):
            return PluginContext(
                event_bus=bus,
                cluster_name="dev",
                config=pcfg,
                get_record=lambda jid: None,
                list_active_records=lambda: [],
                list_records=lambda: [],
            )

        names = mgr.load(
            ["nerve"],
            ctx_factory=ctx_factory,
            configs={"nerve": {"enabled": False}},
        )
        assert names == []


class TestConfigPlugins:
    def test_parse_plugins_section(self, tmp_path: Path):
        p = tmp_path / "config.yaml"
        p.write_text(
            "plugins:\n"
            "  nerve:\n"
            "    enabled: true\n"
            "    expand_threshold: 4\n"
            "  other:\n"
            "    enabled: false\n"
        )
        cfg = load_config(p)
        assert cfg.plugins["nerve"]["expand_threshold"] == 4
        assert enabled_plugin_names(cfg.plugins) == ["nerve"]

    def test_default_official_when_empty(self):
        assert enabled_plugin_names({}, default_official=["nerve"]) == ["nerve"]

    def test_empty_config_plugins_default(self, tmp_path: Path):
        p = tmp_path / "config.yaml"
        p.write_text("")
        cfg = load_config(p)
        assert cfg == MolqConfig(profiles={}, plugins={})


class TestNerveMapping:
    def test_facets_running(self):
        f = facets_for_state(JobState.RUNNING)
        assert f["lifecycle"] == "active"
        assert f["current"]["type"] == "running"

    def test_facets_failed(self):
        f = facets_for_state(JobState.FAILED)
        assert f["lifecycle"] == "ended"
        assert f["outcome"] == "failure"

    def test_expand_few_jobs_as_leaves(self):
        records = [
            _record("a", JobState.RUNNING),
            _record("b", JobState.QUEUED),
        ]
        snaps = build_snapshots(
            records=records,
            cluster_name="dev",
            expand_threshold=8,
            show_members="attention",
            version=1,
            force_end=False,
            alias="test-host",
        )
        assert len(snaps) == 2
        assert all(s["extensions"]["role"] == "job" for s in snaps)
        assert all(s["extensions"]["paintRibbon"] is True for s in snaps)

    def test_rollup_many_jobs_to_group(self):
        records = [
            _record(f"j{i}", JobState.RUNNING if i < 5 else JobState.QUEUED)
            for i in range(20)
        ]
        snaps = build_snapshots(
            records=records,
            cluster_name="dev",
            expand_threshold=8,
            show_members="attention",
            version=2,
            force_end=False,
            alias="test-host",
        )
        groups = [s for s in snaps if s["extensions"].get("role") == "group"]
        assert len(groups) == 1
        g = groups[0]
        assert g["kind"] in ("queue", "batch")
        assert g["progress"]["kind"] == "determinate"
        assert g["extensions"]["memberCount"] == 20
        # no failures → no member leaves under show_members=attention
        members = [s for s in snaps if s["extensions"].get("role") == "member"]
        assert members == []

    def test_rollup_includes_failed_members(self):
        records = [_record(f"j{i}", JobState.RUNNING) for i in range(10)]
        records.append(_record("bad", JobState.FAILED))
        snaps = build_snapshots(
            records=records,
            cluster_name="dev",
            expand_threshold=8,
            show_members="attention",
            version=3,
            force_end=False,
            alias="test-host",
        )
        members = [s for s in snaps if s["extensions"].get("role") == "member"]
        assert len(members) == 1
        assert members[0]["extensions"]["paintRibbon"] is False
        assert members[0]["outcome"] == "failure"

    def test_batch_id_groups_separately(self):
        records = [
            _record("a1", JobState.RUNNING, metadata={"batch_id": "b1"}),
            _record("a2", JobState.RUNNING, metadata={"batch_id": "b1"}),
            _record("b1", JobState.QUEUED, metadata={"batch_id": "b2"}),
            _record("b2", JobState.QUEUED, metadata={"batch_id": "b2"}),
            _record("b3", JobState.QUEUED, metadata={"batch_id": "b2"}),
            _record("b4", JobState.QUEUED, metadata={"batch_id": "b2"}),
            _record("b5", JobState.QUEUED, metadata={"batch_id": "b2"}),
            _record("b6", JobState.QUEUED, metadata={"batch_id": "b2"}),
            _record("b7", JobState.QUEUED, metadata={"batch_id": "b2"}),
            _record("b8", JobState.QUEUED, metadata={"batch_id": "b2"}),
            _record("b9", JobState.QUEUED, metadata={"batch_id": "b2"}),
        ]
        snaps = build_snapshots(
            records=records,
            cluster_name="dev",
            expand_threshold=8,
            show_members="never",
            version=1,
            force_end=False,
            alias="h",
        )
        groups = [s for s in snaps if s["extensions"].get("role") == "group"]
        assert len(groups) == 2

    def test_chain_stage_summary_and_members(self):
        records = [
            _record(
                "r1",
                JobState.SUCCEEDED,
                metadata={},
            ),
            _record("r2", JobState.RUNNING, metadata={}),
            _record("r3", JobState.QUEUED, metadata={}),
        ]
        # Force chain grouping via root_job_id
        records = [
            JobRecord(
                job_id=r.job_id,
                cluster_name=r.cluster_name,
                scheduler=r.scheduler,
                state=r.state,
                command_display=r.command_display,
                root_job_id="r1",
                attempt=i + 1,
                submitted_at=float(i),
            )
            for i, r in enumerate(records)
        ]
        snaps = build_snapshots(
            records=records,
            cluster_name="dev",
            expand_threshold=1,  # force rollup
            show_members="never",  # chain still emits members
            version=1,
            force_end=False,
            alias="h",
        )
        groups = [s for s in snaps if s["extensions"].get("role") == "group"]
        assert len(groups) == 1
        g = groups[0]
        assert g["kind"] == "chain"
        assert "stage" in g["current"]["summary"]
        assert g["extensions"].get("stageCount") == 3
        members = [s for s in snaps if s["extensions"].get("role") == "member"]
        assert len(members) == 3
        assert all(m.get("actions") == [] for m in members)


class TestNervePluginPost:
    def test_status_change_posts_snapshot(self, monkeypatch):
        posted: list[dict] = []

        def fake_urlopen(req, timeout=0.5):
            body = req.data
            import json

            posted.append(json.loads(body.decode()))

            class Resp:
                def read(self):
                    return b"{}"

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

            return Resp()

        monkeypatch.setattr("molq.plugins.nerve.urllib.request.urlopen", fake_urlopen)

        bus = EventBus()
        rec = _record("x", JobState.RUNNING)
        records = {"x": rec}
        plugin = create_plugin("nerve")
        ctx = PluginContext(
            event_bus=bus,
            cluster_name="dev",
            config={"debounce_seconds": 0.01, "alias": "testhost"},
            get_record=lambda jid: records.get(jid),
            list_active_records=lambda: [records["x"]],
            list_records=lambda: [records["x"]],
        )
        plugin.attach(ctx)
        bus.emit(
            EventType.STATUS_CHANGE,
            EventPayload(
                event=EventType.STATUS_CHANGE,
                job_id="x",
                record=rec,
            ),
        )
        # Wait for debounce timer
        import time

        time.sleep(0.15)
        plugin.detach()
        assert posted, "expected at least one snapshot POST"
        jobs = posted[-1]["jobs"]
        assert jobs
        assert posted[-1]["alias"] == "testhost"
