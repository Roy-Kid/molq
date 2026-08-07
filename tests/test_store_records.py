"""Tests for molq.store.records — row mapping and dependency evaluation."""

from __future__ import annotations

import pytest

from molq.status import JobState
from molq.store.records import (
    coerce_job_state,
    dependency_relation_state,
    row_to_record,
)


class _Row(dict):
    """Stands in for sqlite3.Row, which is also subscript-by-name."""


def _row(**overrides):
    base = {
        "job_id": "j1",
        "cluster_name": "dev",
        "scheduler": "local",
        "state": "running",
        "scheduler_job_id": "123",
        "submitted_at": 1.0,
        "started_at": 2.0,
        "finished_at": None,
        "exit_code": None,
        "failure_reason": None,
        "cwd": "/work",
        "command_type": "argv",
        "command_display": "echo hi",
        "metadata": '{"k": "v"}',
        "root_job_id": "j1",
        "attempt": 1,
        "previous_attempt_job_id": None,
        "retry_group_id": "j1",
        "profile_name": None,
        "cleaned_at": None,
    }
    base.update(overrides)
    return _Row(base)


class TestRowToRecord:
    def test_maps_fields(self):
        record = row_to_record(_row())
        assert record.job_id == "j1"
        assert record.state == JobState.RUNNING
        assert record.metadata == {"k": "v"}

    def test_unknown_state_degrades_to_lost(self):
        # A row written by a newer molq must still be listable.
        assert row_to_record(_row(state="teleported")).state == JobState.LOST

    def test_missing_metadata_becomes_empty_dict(self):
        assert row_to_record(_row(metadata=None)).metadata == {}

    def test_blank_root_job_id_falls_back_to_job_id(self):
        assert row_to_record(_row(root_job_id="")).root_job_id == "j1"

    def test_null_attempt_defaults_to_one(self):
        assert row_to_record(_row(attempt=None)).attempt == 1


class TestCoerceJobState:
    def test_valid_value(self):
        assert coerce_job_state("succeeded") == JobState.SUCCEEDED

    def test_none_is_lost(self):
        assert coerce_job_state(None) == JobState.LOST

    def test_garbage_is_lost(self):
        assert coerce_job_state("not-a-state") == JobState.LOST


class TestDependencyRelationState:
    @pytest.mark.parametrize(
        ("state", "expected"),
        [
            (JobState.SUCCEEDED, "satisfied"),
            (JobState.FAILED, "impossible"),
            (JobState.CANCELLED, "impossible"),
            (JobState.RUNNING, "pending"),
            (JobState.QUEUED, "pending"),
        ],
    )
    def test_after_success(self, state, expected):
        assert dependency_relation_state("after_success", state, None) == expected

    @pytest.mark.parametrize(
        ("state", "expected"),
        [
            (JobState.FAILED, "satisfied"),
            (JobState.CANCELLED, "satisfied"),
            (JobState.TIMED_OUT, "satisfied"),
            (JobState.LOST, "satisfied"),
            (JobState.SUCCEEDED, "impossible"),
            (JobState.RUNNING, "pending"),
        ],
    )
    def test_after_failure(self, state, expected):
        assert dependency_relation_state("after_failure", state, None) == expected

    def test_after_started_uses_the_timestamp(self):
        assert dependency_relation_state("after_started", JobState.QUEUED, 1.0) == (
            "satisfied"
        )

    def test_after_started_pending_without_start(self):
        assert dependency_relation_state("after_started", JobState.QUEUED, None) == (
            "pending"
        )

    def test_after_started_satisfied_once_running(self):
        assert dependency_relation_state("after_started", JobState.RUNNING, None) == (
            "satisfied"
        )

    @pytest.mark.parametrize(
        ("state", "expected"),
        [
            (JobState.SUCCEEDED, "satisfied"),
            (JobState.FAILED, "satisfied"),
            (JobState.RUNNING, "pending"),
        ],
    )
    def test_after_any_terminal_state(self, state, expected):
        assert dependency_relation_state("after", state, None) == expected

    def test_unknown_condition_raises(self):
        with pytest.raises(ValueError, match="Unknown dependency condition"):
            dependency_relation_state("after_lunch", JobState.RUNNING, None)
