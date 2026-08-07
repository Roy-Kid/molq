"""Tests for molq.dashboard — the terminal monitor.

The key-reader loop needs a TTY and is left to manual testing; everything
below it (state building, formatting, rendering) is exercised here by
rendering into a non-TTY Console and reading the text back.
"""

from __future__ import annotations

import pytest
from rich.console import Console

from molq.dashboard import (
    DashboardState,
    DependencyLine,
    JobRow,
    MolqMonitor,
    RunDashboard,
    _dependency_marker,
    _dependency_summary,
    _elapsed_ts,
    _molq_overall_status,
    _UIState,
)
from molq.models import Command, DependencyPreview, JobDependency, JobSpec
from molq.status import JobState
from molq.store import JobStore


def _render_to_text(renderable, width: int = 120) -> str:
    console = Console(width=width, file=None, record=True, force_terminal=False)
    with console.capture() as capture:
        console.print(renderable)
    return capture.get()


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestElapsed:
    def test_none_start_is_none(self):
        assert _elapsed_ts(None) is None

    def test_seconds(self):
        assert _elapsed_ts(1000.0, 1030.0) == "30s"

    def test_minutes(self):
        assert _elapsed_ts(1000.0, 1000.0 + 95) == "1m 35s"

    def test_hours(self):
        assert _elapsed_ts(1000.0, 1000.0 + 3 * 3600 + 4 * 60) == "3h 04m"

    def test_negative_span_clamps_to_zero(self):
        assert _elapsed_ts(2000.0, 1000.0) == "0s"

    def test_running_job_uses_now(self):
        # No finish time: elapsed is measured against the clock, so it parses.
        assert _elapsed_ts(1000.0) is not None


class TestOverallStatus:
    def test_running_wins(self):
        assert _molq_overall_status(1, 5, 3, 2) == "running"

    def test_pending_when_nothing_runs(self):
        assert _molq_overall_status(0, 2, 0, 0) == "pending"

    def test_failed_when_only_failures(self):
        assert _molq_overall_status(0, 0, 3, 0) == "failed"

    def test_mixed_when_some_succeeded(self):
        assert _molq_overall_status(0, 0, 1, 2) == "mixed"

    def test_done_when_all_succeeded(self):
        assert _molq_overall_status(0, 0, 0, 4) == "done"


class TestDependencySummary:
    def test_none_preview(self):
        assert _dependency_summary(None) is None

    def test_no_edges(self):
        assert _dependency_summary(DependencyPreview(job_id="j")) is None

    def test_upstream_only(self):
        preview = DependencyPreview(job_id="j", upstream_total=3, upstream_satisfied=1)
        assert _dependency_summary(preview) == "1/3 ok"

    def test_downstream_only(self):
        preview = DependencyPreview(job_id="j", downstream_total=2)
        assert _dependency_summary(preview) == "-> 2"

    def test_both_directions(self):
        preview = DependencyPreview(
            job_id="j", upstream_total=2, upstream_satisfied=2, downstream_total=5
        )
        assert _dependency_summary(preview) == "2/2 +5"


class TestDependencyMarker:
    @pytest.mark.parametrize(
        ("relation", "marker"),
        [("satisfied", "✓"), ("pending", "·"), ("impossible", "!"), ("weird", "·")],
    )
    def test_marker(self, relation, marker):
        assert _dependency_marker(relation) == marker


# ---------------------------------------------------------------------------
# UI navigation state
# ---------------------------------------------------------------------------


class TestUIState:
    def test_starts_at_first_row_in_list_view(self):
        ui = _UIState()
        assert ui.selected == 0
        assert ui.detail is False

    def test_move_down_is_bounded_by_total(self):
        ui = _UIState()
        ui.update_total(2)
        ui.move_down()
        ui.move_down()
        ui.move_down()
        assert ui.selected == 1

    def test_move_up_stops_at_zero(self):
        ui = _UIState()
        ui.update_total(3)
        ui.move_down()
        ui.move_up()
        ui.move_up()
        assert ui.selected == 0

    def test_detail_toggles(self):
        ui = _UIState()
        ui.update_total(1)
        ui.toggle_detail()
        assert ui.detail is True
        ui.toggle_detail()
        assert ui.detail is False

    def test_detail_cannot_open_with_no_rows(self):
        ui = _UIState()
        ui.update_total(0)
        ui.toggle_detail()
        assert ui.detail is False

    def test_exit_detail(self):
        ui = _UIState()
        ui.update_total(1)
        ui.toggle_detail()
        ui.exit_detail()
        assert ui.detail is False

    def test_shrinking_list_clamps_selection(self):
        ui = _UIState()
        ui.update_total(5)
        ui.move_down()
        ui.move_down()
        ui.update_total(2)
        assert ui.selected == 1

    def test_emptying_list_resets_and_closes_detail(self):
        ui = _UIState()
        ui.update_total(3)
        ui.toggle_detail()
        ui.update_total(0)
        assert ui.selected == 0
        assert ui.detail is False


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _state(**overrides) -> DashboardState:
    base = dict(
        title="molq",
        overall_status="running",
        total=2,
        running=1,
        pending=1,
        done=0,
        failed=0,
        updated_at="14:32:07",
        jobs=(
            JobRow(
                state="running",
                run_id="abc123",
                cluster="hpc",
                scheduler_id="88001",
                elapsed="1m 23s",
                dependency_summary="1/2 ok",
                extras=(("command", "python train.py"),),
                upstream=(
                    DependencyLine(
                        marker="✓",
                        job_id="up-1",
                        dependency_type="after_success",
                        job_state="succeeded",
                        scheduler_dependency="afterok:1",
                    ),
                ),
                downstream=(
                    DependencyLine(
                        marker="·",
                        job_id="down-1",
                        dependency_type="after_success",
                        job_state="queued",
                    ),
                ),
            ),
            JobRow(state="pending", run_id="def456", message="waiting"),
        ),
    )
    base.update(overrides)
    return DashboardState(**base)


class TestRendering:
    def test_list_view_shows_every_job(self):
        text = _render_to_text(RunDashboard()._render(_state(), _UIState()))
        assert "ABC123" not in text  # ids are not upper-cased
        assert "abc123" in text
        assert "def456" in text
        assert "RUNNING" in text

    def test_header_carries_title_and_timestamp(self):
        text = _render_to_text(RunDashboard()._render_header(_state()))
        assert "molq" in text
        assert "14:32:07" in text
        assert "RUNNING" in text

    def test_overview_shows_counts(self):
        text = _render_to_text(RunDashboard()._render_overview(_state()))
        assert "total" in text
        assert "running" in text

    def test_empty_list_renders_placeholder(self):
        text = _render_to_text(RunDashboard()._render_jobs(_state(jobs=()), 0))
        assert "no jobs" in text

    def test_detail_view_shows_dependencies(self):
        ui = _UIState()
        ui.update_total(2)
        ui.toggle_detail()
        text = _render_to_text(RunDashboard()._render(_state(), ui))
        assert "Detail" in text
        assert "upstream" in text
        assert "downstream" in text
        assert "up-1" in text

    def test_detail_view_shows_extras(self):
        text = _render_to_text(RunDashboard()._render_detail(_state().jobs[0]))
        assert "command" in text
        assert "python train.py" in text

    def test_detail_view_shows_failure_note(self):
        row = JobRow(state="failed", run_id="x", message="exit code 1")
        text = _render_to_text(RunDashboard()._render_detail(row))
        assert "exit code 1" in text

    def test_footer_changes_between_views(self):
        list_footer = _render_to_text(RunDashboard()._render_footer(False))
        detail_footer = _render_to_text(RunDashboard()._render_footer(True))
        assert "open detail" in list_footer
        assert "back to list" in detail_footer


# ---------------------------------------------------------------------------
# MolqMonitor state building
# ---------------------------------------------------------------------------


@pytest.fixture
def populated_db(tmp_path):
    db = tmp_path / "jobs.db"
    store = JobStore(db)

    def add(job_id, state, cluster="hpc", **kwargs):
        store.insert_job(
            JobSpec(
                job_id=job_id,
                cluster_name=cluster,
                scheduler="slurm",
                command=Command.from_submit_args(argv=["python", "train.py"]),
            )
        )
        store.update_job(job_id, state=state, **kwargs)

    add("run-1", JobState.RUNNING, scheduler_job_id="88001")
    add("queue-1", JobState.QUEUED)
    add("ok-1", JobState.SUCCEEDED, finished_at=2_000_000_000.0)
    add("bad-1", JobState.FAILED, finished_at=2_000_000_000.0, exit_code=1)
    store.add_dependencies(
        "queue-1",
        [
            JobDependency(
                job_id="queue-1",
                dependency_job_id="run-1",
                dependency_type="after_success",
                scheduler_dependency="afterok:88001",
            )
        ],
    )
    store.close()
    return db


class TestMolqMonitorState:
    def _build(self, db, **kwargs):
        """Run MolqMonitor.watch() but capture the state instead of drawing it."""
        monitor = MolqMonitor(db_path=str(db), **kwargs)
        captured = {}

        # Replaces the bound method, so it receives the RunDashboard as self.
        def fake_watch(_self, data_fn, *, refresh_interval):
            captured["state"] = data_fn()

        import molq.dashboard as dashboard_module

        original = dashboard_module.RunDashboard.watch
        dashboard_module.RunDashboard.watch = fake_watch
        try:
            monitor.watch()
        finally:
            dashboard_module.RunDashboard.watch = original
        return captured["state"]

    def test_active_only_by_default(self, populated_db):
        state = self._build(populated_db)
        ids = {row.run_id for row in state.jobs}
        assert "run-1" in ids
        assert "ok-1" not in ids

    def test_include_terminal_shows_everything(self, populated_db):
        state = self._build(populated_db, include_terminal=True)
        ids = {row.run_id for row in state.jobs}
        assert {"run-1", "queue-1", "ok-1", "bad-1"} <= ids
        assert "all jobs" in state.title

    def test_counts_are_bucketed(self, populated_db):
        state = self._build(populated_db, include_terminal=True)
        assert state.running == 1
        assert state.pending == 1
        assert state.done == 1
        assert state.failed == 1
        assert state.total == 4

    def test_limit_is_applied(self, populated_db):
        state = self._build(populated_db, include_terminal=True, limit=2)
        assert len(state.jobs) == 2

    def test_dependency_summary_is_attached(self, populated_db):
        state = self._build(populated_db, include_terminal=True)
        row = next(r for r in state.jobs if r.run_id == "queue-1")
        assert row.dependency_summary is not None
        assert row.upstream

    def test_extras_carry_command_and_exit_code(self, populated_db):
        state = self._build(populated_db, include_terminal=True)
        row = next(r for r in state.jobs if r.run_id == "bad-1")
        extras = dict(row.extras)
        assert extras["command"] == "python train.py"
        assert extras["exit code"] == "1"

    def test_overall_status_reflects_the_set(self, populated_db):
        state = self._build(populated_db, include_terminal=True)
        assert state.overall_status == "running"

    def test_empty_database_renders(self, tmp_path):
        db = tmp_path / "empty.db"
        JobStore(db).close()
        state = self._build(db)
        assert state.jobs == ()
        assert state.total == 0
