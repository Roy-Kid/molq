"""All Slurm resource/directive/dependency/step/state semantics."""

from __future__ import annotations

import builtins
import shlex

from molq.errors import MolqError
from molq.scheduler.base import TERMINAL, NativeJob, _SchedulerMethods
from molq.scheduler.execution import render_execution

STATES = {
    "PENDING": "queued",
    "CONFIGURING": "queued",
    "RUNNING": "running",
    "COMPLETING": "running",
    "SUSPENDED": "running",
    "COMPLETED": "succeeded",
    "FAILED": "failed",
    "NODE_FAIL": "failed",
    "OUT_OF_MEMORY": "failed",
    "BOOT_FAIL": "failed",
    "CANCELLED": "cancelled",
    "PREEMPTED": "cancelled",
    "TIMEOUT": "timed_out",
    "DEADLINE": "timed_out",
}
DEPENDENCIES = {
    "after": "afterany",
    "after_success": "afterok",
    "after_failure": "afternotok",
}


class SlurmScheduler(_SchedulerMethods):
    """Submit/query/cancel through the injected Transport, with no capabilities."""

    def launch(self, unit: dict, payload: str) -> str:
        """Map native steps and explicit MPI launch, without probing tools."""
        intent = unit.get("launch", {"kind": "direct"})
        placement = unit.get("placement")
        if intent["kind"] == "mpi" and self.cluster.get("launcher") == "srun":
            return f"srun --exclusive --ntasks={intent['ranks']} --cpus-per-task={intent.get('threads', 1)} {payload}"
        if intent["kind"] == "direct" and placement:
            if placement.get("tasks", 1) != 1:
                self.unsupported(
                    "Direct placement is exactly one task; use MPI for multiple ranks"
                )
            return f"srun --exclusive --ntasks=1 --cpus-per-task={placement.get('cpus_per_task', 1)} {payload}"
        return super().launch(unit, payload)

    def validate(self, spec: dict) -> None:
        """Validate exact representability, never real cluster configuration."""
        super().validate(spec)
        resources = spec["resources"]
        if (
            resources.get("nodes", 1) > 1
            and len(spec["execution"]["units"]) > 1
            and any(
                u.get("launch", {}).get("kind", "direct") == "direct"
                and not u.get("placement")
                for u in spec["execution"]["units"]
            )
        ):
            self.unsupported(
                "Multi-node direct units require explicit native-step placement"
            )
        if len(spec["execution"]["units"]) > 1 and "tasks" not in resources:
            raise MolqError(
                "RESOURCE_REQUEST_INVALID",
                "Multi-unit batch execution requires an explicit task budget",
            )
        for unit in spec["execution"]["units"]:
            launch = unit.get("launch", {})
            if launch.get("ranks", 1) > resources.get("tasks", 1) or launch.get(
                "threads", 1
            ) > resources.get("cpus_per_task", 1):
                raise MolqError(
                    "EXECUTION_RESOURCE_CONFLICT",
                    "MPI launch exceeds the allocation layout",
                )
        accelerators = resources.get("accelerators", [])
        if len(accelerators) > 1:
            self.unsupported(
                "Multiple accelerator requests require an unambiguous native resource mapping"
            )
        if (
            accelerators
            and accelerators[0]["kind"] == "nvidia_mps"
            and accelerators[0]["scope"] != "per_node"
        ):
            self.unsupported("Slurm MPS is represented per node")
        for edge in spec["scheduling"].get("dependencies", []):
            if edge["condition"] not in DEPENDENCIES:
                self.unsupported("This dependency condition has no exact Slurm mapping")

    def render(self, spec: dict, directory: str) -> str:
        """Render allocation resources and plan in one Slurm job script."""
        self.validate(spec)
        r, s = spec["resources"], spec["scheduling"]
        directives = [
            f"--chdir={shlex.quote(directory)}",
            f"--output={shlex.quote(directory + '/stdout')}",
            f"--error={shlex.quote(directory + '/stderr')}",
        ]
        for field, flag in [
            ("nodes", "nodes"),
            ("tasks", "ntasks"),
            ("cpus_per_task", "cpus-per-task"),
        ]:
            if field in r:
                directives.append(f"--{flag}={r[field]}")
        if "memory_bytes" in r:
            directives.append(
                f"--mem={((int(r['memory_bytes']) + 1048575) // 1048576)}M"
            )
        if seconds := r.get("time_limit_seconds"):
            directives.append(
                f"--time={seconds // 3600}:{seconds % 3600 // 60:02}:{seconds % 60:02}"
            )
        for field, flag in [
            ("name", "job-name"),
            ("partition", "partition"),
            ("account", "account"),
            ("qos", "qos"),
            ("reservation", "reservation"),
            ("priority", "priority"),
        ]:
            if field in s:
                directives.append(f"--{flag}={s[field]}")
        if s.get("exclusive"):
            directives.append("--exclusive")
        for a in r.get("accelerators", []):
            if a["kind"] == "nvidia_mps":
                directives.append(f"--gres=mps:{a['quantity']}")
            else:
                resource = f"{a.get('model', '') + ':' if a.get('model') else ''}{a['quantity']}"
                directives.append(
                    f"--{'gpus-per-node' if a['scope'] == 'per_node' else 'gpus'}={resource}"
                )
        if edges := s.get("dependencies"):
            directives.append(
                "--dependency="
                + ",".join(
                    f"{DEPENDENCIES[e['condition']]}:{e['ref']['native_id']}"
                    for e in edges
                )
            )
        return (
            "#!/usr/bin/env bash\n"
            + "\n".join("#SBATCH " + d for d in directives)
            + "\n"
            + render_execution(spec, self.launch)
        )

    async def submit(self, spec: dict, directory: str) -> NativeJob:
        """Return verified native identity; unavailable evidence is outcome unknown."""
        path = await self.stage(spec, directory)
        text = await self.native(["sbatch", "--parsable", path], mutation=True)
        identity = text.strip().split(";")[0]
        if not identity.isdigit():
            raise MolqError(
                "OUTCOME_UNKNOWN",
                "Cannot parse accepted allocation identity",
                outcome="unknown",
            )
        return await self.accepted_identity(identity)

    @staticmethod
    def _parse(text: str, source: str) -> dict[str, NativeJob]:
        jobs = {}
        for line in text.splitlines():
            fields = line.split("|")
            if len(fields) < 5:
                raise MolqError(
                    "SCHEDULER_UNAVAILABLE", "Incomplete Slurm query response"
                )
            identity, raw, submit, cwd, name = fields[:5]
            if "." in identity:  # accounting step rows are not allocations
                continue
            if not raw.strip():
                raise MolqError("SCHEDULER_UNAVAILABLE", "Missing Slurm native state")
            state = STATES.get(raw.split()[0].rstrip("+"), "unknown")
            code = None
            if len(fields) > 5 and fields[5]:
                try:
                    status, signal = fields[5].split(":")
                    code = int(status) or (128 + int(signal) if int(signal) else 0)
                except ValueError:
                    raise MolqError(
                        "SCHEDULER_UNAVAILABLE", "Invalid Slurm accounting exit code"
                    ) from None
            if submit in {"", "Unknown", "N/A"}:
                submit = ""
            jobs[identity] = NativeJob(
                identity,
                submit,
                state,
                source,
                raw,
                code,
                cwd if cwd not in {"", "Unknown"} else None,
                name,
            )
        return jobs

    async def query_many(self, ids: builtins.list[str]) -> dict[str, NativeJob]:
        """Batch queue query with accounting for missing allocations."""
        if not ids:
            return {}
        try:
            text = await self.native(
                [
                    "squeue",
                    "--noheader",
                    "--jobs",
                    ",".join(ids),
                    "--format=%i|%T|%V|%Z|%j",
                ]
            )
        except MolqError as exc:
            # Single-ID queue lookups can reject a purged finished allocation.
            # Only native absence permits accounting; an outage remains an error.
            if exc.context.get(
                "returncode"
            ) != 1 or "Invalid job id specified" not in exc.context.get("stderr", ""):
                raise
            return await self.history(ids)
        jobs = self._parse(text, "queue")
        missing = [i for i in ids if i not in jobs]
        if missing:
            jobs.update(await self.history(missing))
        return {i: j for i, j in jobs.items() if i in ids}

    async def list(self) -> builtins.list[NativeJob]:
        """Read this native account's queue, including externally submitted jobs."""
        return list(
            self._parse(
                await self.native(
                    ["squeue", "--me", "--noheader", "--format=%i|%T|%V|%Z|%j"]
                ),
                "queue",
            ).values()
        )

    async def history(self, ids: builtins.list[str]) -> dict[str, NativeJob]:
        """Query live accounting, without a mirrored history database."""
        if not ids:
            return {}
        text = await self.native(
            [
                "sacct",
                "--allocations",
                "--noheader",
                "--parsable2",
                "--jobs",
                ",".join(ids),
                "--format=JobIDRaw,State,Submit,WorkDir,JobName,ExitCode",
            ]
        )
        return self._parse(text, "accounting")

    async def cancel(self, job: NativeJob) -> dict:
        """Return request acceptance; actual state requires another native query."""
        if job.state in TERMINAL:
            return {"outcome": "already_terminal"}
        try:
            await self.native(["scancel", job.native_id], mutation=True)
        except MolqError as exc:
            if exc.kind == "SUBMISSION_REJECTED":
                raise MolqError(
                    "CANCEL_REJECTED", "Native cancellation rejected", **exc.context
                ) from exc
            raise
        return {"outcome": "accepted"}
