"""Native syntax and state truth are owned exclusively by Scheduler."""

import asyncio
import copy
import json

import pytest
from conftest import FakeTransport

from molq.errors import MolqError
from molq.scheduler import LSFScheduler, PBSScheduler, ShellScheduler, SlurmScheduler
from molq.scheduler.base import NativeJob
from molq.transport import Result


def run(awaitable):
    return asyncio.run(awaitable)


@pytest.mark.parametrize("scheduler", [SlurmScheduler, PBSScheduler, LSFScheduler])
def test_cancel_ack_is_not_terminal(scheduler, spec):
    transport = FakeTransport()
    target = scheduler(transport, {"pbs_dialect": "openpbs"})
    result = run(target.cancel(NativeJob("123", "timestamp", "running", "queue")))
    assert result == {"outcome": "accepted"}
    assert len(transport.calls) == 1


@pytest.mark.parametrize("scheduler", [SlurmScheduler, PBSScheduler, LSFScheduler])
def test_cancel_failure_is_explicit(scheduler):
    transport = FakeTransport([Result(1, b"", b"denied")])
    target = scheduler(transport, {})
    with pytest.raises(MolqError) as e:
        run(target.cancel(NativeJob("123", "timestamp", "running", "queue")))
    assert e.value.kind == "CANCEL_REJECTED"


@pytest.mark.parametrize("scheduler", [SlurmScheduler, PBSScheduler, LSFScheduler])
def test_cancel_network_failure_is_unknown(scheduler):
    transport = FakeTransport([Result(255, b"", b"SSH failed")])
    with pytest.raises(MolqError) as e:
        run(
            scheduler(transport, {}).cancel(
                NativeJob("123", "timestamp", "running", "queue")
            )
        )
    assert e.value.kind == "OUTCOME_UNKNOWN"
    assert e.value.outcome == "unknown"


@pytest.mark.parametrize("scheduler", [SlurmScheduler, PBSScheduler, LSFScheduler])
def test_query_error_is_not_empty_or_lost(scheduler):
    transport = FakeTransport([Result(1, b"", b"unavailable")])
    with pytest.raises(MolqError) as e:
        run(scheduler(transport, {}).query_many(["123"]))
    assert e.value.kind == "SCHEDULER_UNAVAILABLE"


def test_slurm_resources_dependencies_mps_and_native_steps(spec):
    spec["resources"] = {
        "nodes": 2,
        "tasks": 4,
        "cpus_per_task": 2,
        "memory_bytes": "1048577",
        "time_limit_seconds": 61,
        "accelerators": [{"kind": "nvidia_mps", "quantity": 20, "scope": "per_node"}],
    }
    spec["scheduling"] = {
        "partition": "gpu",
        "account": "science",
        "priority": 0,
        "dependencies": [{"condition": "after_success", "ref": {"native_id": "42"}}],
    }
    spec["execution"]["units"][0]["launch"] = {"kind": "mpi", "ranks": 4, "threads": 2}
    target = SlurmScheduler(FakeTransport(), {"launcher": "srun"})
    script = target.render(spec, "/target/a b")
    for expected in [
        "--nodes=2",
        "--ntasks=4",
        "--cpus-per-task=2",
        "--mem=2M",
        "--time=0:01:01",
        "--gres=mps:20",
        "--dependency=afterok:42",
        "--priority=0",
        "srun --exclusive --ntasks=4",
        "export OMP_NUM_THREADS=2",
    ]:
        assert expected in script
    assert "nvidia-cuda-mps-control" not in script


def test_slurm_gpu_total_model_and_no_fake_feature_inventory(spec):
    target = SlurmScheduler(FakeTransport(), {})
    spec["resources"]["accelerators"] = [
        {"kind": "gpu", "quantity": 2, "scope": "total", "model": "a100"}
    ]
    assert "--gpus=a100:2" in target.render(spec, "/target")
    assert not hasattr(target, "capabilities")


@pytest.mark.parametrize("scope", ["total"])
def test_mps_unrepresentable_scope_rejected(spec, scope):
    spec["resources"]["accelerators"] = [
        {"kind": "nvidia_mps", "quantity": 20, "scope": scope}
    ]
    with pytest.raises(MolqError, match="per node"):
        SlurmScheduler(FakeTransport(), {}).validate(spec)


def test_slurm_queue_absence_uses_accounting_and_ignores_steps():
    transport = FakeTransport(
        [
            "123|RUNNING|2026-10-07T12:00:00|/target/job|one\n",
            "124|COMPLETED|2026-10-07T12:00:01|/target/job2|two|0:0\n124.batch|FAILED|x|x|x|1:0\n",
        ]
    )
    jobs = run(SlurmScheduler(transport, {}).query_many(["123", "124"]))
    assert jobs["123"].state == "running"
    assert jobs["124"].state == "succeeded"
    assert jobs["124"].incarnation == "2026-10-07T12:00:01"
    assert len(transport.calls) == 2
    assert transport.calls[1][0][0] == "sacct"


def test_slurm_submit_uses_same_renderer_and_verified_identity(spec):
    transport = FakeTransport(
        ["123;cluster", "123|PENDING|2026-10-07T12:00:00|/target/job|test"]
    )
    target = SlurmScheduler(transport, {})
    job = run(target.submit(spec, "/target/job"))
    assert job.native_id == "123"
    assert b"#SBATCH" in transport.files["/target/job/job.sh"]
    assert transport.calls[0][0] == ["sbatch", "--parsable", "/target/job/job.sh"]


@pytest.mark.parametrize("text", ["wrong", "1|COMPLETED|t|/tmp|job|broken"])
def test_slurm_malformed_output_not_terminal(text):
    with pytest.raises(MolqError):
        SlurmScheduler._parse(text, "accounting")


def test_pbs_render_and_finished_truth(spec):
    spec["resources"] = {
        "nodes": 2,
        "tasks": 4,
        "cpus_per_task": 2,
        "memory_bytes": "1048577",
        "accelerators": [{"kind": "gpu", "quantity": 1, "scope": "per_node"}],
        "time_limit_seconds": 120,
    }
    spec["scheduling"] = {
        "name": "hello",
        "partition": "normal",
        "account": "science",
        "priority": 10,
        "dependencies": [{"condition": "after", "ref": {"native_id": "7.host"}}],
    }
    target = PBSScheduler(FakeTransport(), {"pbs_dialect": "openpbs"})
    script = target.render(spec, "/target/job")
    assert "select=2:ncpus=4:mpiprocs=2:ompthreads=2:mem=2mb:ngpus=1" in script
    assert "depend=afterany:7.host" in script
    jobs = target._parse(
        json.dumps(
            {
                "Jobs": {
                    "123.host": {
                        "job_state": "F",
                        "ctime": 123456,
                        "Exit_status": 0,
                        "Output_Path": "host:/target/job/stdout",
                    }
                }
            }
        ),
        "accounting",
    )
    assert jobs["123.host"].state == "succeeded"
    assert jobs["123.host"].workdir == "/target/job"
    unknown = target._parse(
        json.dumps({"Jobs": {"1.host": {"job_state": "F", "ctime": 1}}}), "accounting"
    )
    assert unknown["1.host"].state == "unknown"


@pytest.mark.parametrize("scheduler", [PBSScheduler, LSFScheduler])
def test_mps_has_no_emulation(spec, scheduler):
    spec["resources"]["accelerators"] = [
        {"kind": "nvidia_mps", "quantity": 20, "scope": "per_node"}
    ]
    with pytest.raises(MolqError) as e:
        scheduler(FakeTransport(), {"pbs_dialect": "openpbs"}).render(spec, "/target")
    assert e.value.kind == "SCHEDULER_UNSUPPORTED"


def test_lsf_directives_and_native_state(spec):
    spec["resources"] = {"tasks": 2, "time_limit_seconds": 61}
    spec["scheduling"] = {
        "name": "one",
        "partition": "normal",
        "account": "project",
        "priority": 4,
        "exclusive": True,
        "dependencies": [{"condition": "after_failure", "ref": {"native_id": "10"}}],
    }
    target = LSFScheduler(FakeTransport(), {})
    script = target.render(spec, "/target/job")
    assert "-W 0:02" in script and "-w 'exit(10)'" in script
    jobs = target._parse(
        json.dumps(
            {
                "RECORDS": [
                    {
                        "JOBID": "10",
                        "STAT": "DONE",
                        "SUBMIT_TIME": "2026-10-07",
                        "CWD": "/target/job",
                        "EXIT_CODE": "0",
                    }
                ]
            }
        )
    )
    assert jobs["10"].state == "succeeded"
    assert jobs["10"].exit_code == 0


@pytest.mark.parametrize("scheduler", [PBSScheduler, LSFScheduler])
def test_invalid_native_json_does_not_invent_state(scheduler):
    with pytest.raises(MolqError):
        scheduler._parse(
            "not-json", "accounting"
        ) if scheduler is PBSScheduler else scheduler._parse("not-json")


def test_shell_rejects_formal_resource_request_and_mpi_without_binding(spec):
    target = ShellScheduler(FakeTransport(), {})
    bad = copy.deepcopy(spec)
    bad["resources"] = {"tasks": 1}
    with pytest.raises(MolqError):
        target.validate(bad)
    spec["execution"]["units"][0]["launch"] = {"kind": "mpi", "ranks": 2}
    with pytest.raises(MolqError):
        target.validate(spec)


@pytest.mark.parametrize(
    "scheduler,accepted",
    [
        (SlurmScheduler, "123"),
        (PBSScheduler, "123.host"),
        (LSFScheduler, "Job <123> is submitted"),
    ],
)
def test_post_acceptance_query_failure_remains_unknown(spec, scheduler, accepted):
    transport = FakeTransport([accepted, Result(1, b"", b"accounting unavailable")])
    with pytest.raises(MolqError) as e:
        run(scheduler(transport, {"pbs_dialect": "openpbs"}).submit(spec, "/target"))
    assert e.value.kind == "OUTCOME_UNKNOWN" and e.value.outcome == "unknown"
    assert "native_id" in e.value.context


def test_slurm_purged_queue_entry_uses_accounting_without_masking_outage():
    transport = FakeTransport(
        [
            Result(1, b"", b"slurm_load_jobs error: Invalid job id specified"),
            "42|COMPLETED|2026-10-07T00:00:00|/target|name|0:0",
        ]
    )
    scheduler = SlurmScheduler(transport, {})
    result = asyncio.run(scheduler.query_many(["42"]))
    assert result["42"].state == "succeeded"
    assert transport.calls[1][0][0] == "sacct"


def test_lsf_log_fields_use_native_output_paths_not_submission_cwd():
    scheduler = LSFScheduler(
        FakeTransport(
            [
                json.dumps(
                    {
                        "RECORDS": [
                            {
                                "JOBID": "42",
                                "STAT": "PEND",
                                "SUBMIT_TIME": "Oct 7 10:00",
                                "EXEC_CWD": "-",
                                "OUTPUT_FILE": "/target/allocation/stdout",
                                "ERROR_FILE": "/target/allocation/stderr",
                            }
                        ]
                    }
                )
            ]
        ),
        {},
    )
    job = asyncio.run(scheduler.query_many(["42"]))["42"]
    assert job.workdir == "/target/allocation"
    assert job.stdout_path == "/target/allocation/stdout"
    assert job.incarnation == "Oct 7 10:00|/target/allocation/stdout"
    assert "exec_cwd output_file error_file" in scheduler.transport.calls[0][0][-2]
