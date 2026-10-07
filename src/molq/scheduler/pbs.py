"""PBS Professional/OpenPBS directives, queries, history and dependencies."""

from __future__ import annotations

import builtins
import json
import shlex

from molq.errors import MolqError
from molq.scheduler.base import TERMINAL, NativeJob, _SchedulerMethods
from molq.scheduler.execution import render_execution

DEPENDENCIES = {
    "after": "afterany",
    "after_success": "afterok",
    "after_failure": "afternotok",
}


class PBSScheduler(_SchedulerMethods):
    """Use explicitly selected OpenPBS JSON/select dialect, with no probing."""

    def validate(self, spec: dict) -> None:
        """Reject requests that cannot be represented in the configured dialect."""
        super().validate(spec)
        if self.cluster.get("pbs_dialect") != "openpbs":
            self.unsupported(
                "PBS requires explicit pbs_dialect=openpbs for JSON/select semantics"
            )
        r, s = spec["resources"], spec["scheduling"]
        nodes, tasks = r.get("nodes", 1), r.get("tasks", 1)
        for unit in spec["execution"]["units"]:
            launch = unit.get("launch", {})
            if launch.get("ranks", 1) > tasks or launch.get("threads", 1) > r.get(
                "cpus_per_task", 1
            ):
                raise MolqError(
                    "EXECUTION_RESOURCE_CONFLICT",
                    "MPI launch exceeds allocation layout",
                )
        if tasks % nodes:
            self.unsupported(
                "OpenPBS requires evenly distributed tasks across requested nodes"
            )
        if len(spec["execution"]["units"]) > 1 and "tasks" not in r:
            raise MolqError(
                "RESOURCE_REQUEST_INVALID",
                "Multi-unit batch execution requires explicit tasks",
            )
        if any(k in s for k in ("qos", "reservation", "exclusive")):
            self.unsupported("These scheduling intents have no configured PBS mapping")
        for a in r.get("accelerators", []):
            if a["kind"] != "gpu" or a["scope"] != "per_node" or "model" in a:
                self.unsupported(
                    "OpenPBS supports only per-node GPU counts in this mapping"
                )
        if len(r.get("accelerators", [])) > 1:
            self.unsupported("Multiple accelerator requests have no exact PBS mapping")
        if any(e["condition"] not in DEPENDENCIES for e in s.get("dependencies", [])):
            self.unsupported("Dependency condition has no exact PBS mapping")

    def render(self, spec: dict, directory: str) -> str:
        """Render one PBS allocation and its internal execution tree."""
        self.validate(spec)
        r, s = spec["resources"], spec["scheduling"]
        nodes, tasks, cpus = (
            r.get("nodes", 1),
            r.get("tasks", 1),
            r.get("cpus_per_task", 1),
        )
        chunk = f"select={nodes}:ncpus={tasks // nodes * cpus}:mpiprocs={tasks // nodes}:ompthreads={cpus}"
        if "memory_bytes" in r:
            chunk += f":mem={((int(r['memory_bytes']) + 1048575) // 1048576)}mb"
        for a in r.get("accelerators", []):
            chunk += f":ngpus={a['quantity']}"
        directives = [
            f"-l {chunk}",
            f"-o {shlex.quote(directory + '/stdout')}",
            f"-e {shlex.quote(directory + '/stderr')}",
        ]
        if seconds := r.get("time_limit_seconds"):
            directives.append(
                f"-l walltime={seconds // 3600}:{seconds % 3600 // 60:02}:{seconds % 60:02}"
            )
        for field, flag in [
            ("name", "N"),
            ("partition", "q"),
            ("account", "A"),
            ("priority", "p"),
        ]:
            if field in s:
                directives.append(f"-{flag} {s[field]}")
        if edges := s.get("dependencies"):
            directives.append(
                "-W depend="
                + ",".join(
                    f"{DEPENDENCIES[e['condition']]}:{e['ref']['native_id']}"
                    for e in edges
                )
            )
        return (
            "#!/usr/bin/env bash\n"
            + "\n".join("#PBS " + d for d in directives)
            + "\ncd -- "
            + shlex.quote(directory)
            + " || exit 126\n"
            + render_execution(spec, self.launch)
        )

    @staticmethod
    def _parse(text: str, source: str) -> dict[str, NativeJob]:
        try:
            rows = json.loads(text)["Jobs"]
            jobs = {}
            for identity, row in rows.items():
                raw = row.get("job_state", "")
                code = row.get("Exit_status")
                state = {
                    "Q": "queued",
                    "H": "queued",
                    "W": "queued",
                    "T": "queued",
                    "R": "running",
                    "E": "running",
                    "S": "running",
                    "B": "running",
                }.get(raw, "unknown")
                if raw in {"F", "C"} and code is not None:
                    state = (
                        "succeeded"
                        if int(code) == 0
                        else ("cancelled" if int(code) == 271 else "failed")
                    )
                cwd = (
                    row.get("Output_Path", "").split(":", 1)[-1].rsplit("/", 1)[0]
                    or None
                )
                jobs[identity] = NativeJob(
                    identity,
                    str(row.get("ctime") or ""),
                    state,
                    source,
                    raw,
                    int(code) if code is not None else None,
                    cwd,
                    row.get("Job_Name"),
                    row.get("Output_Path", "").split(":", 1)[-1] or None,
                    row.get("Error_Path", "").split(":", 1)[-1] or None,
                )
            return jobs
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise MolqError(
                "SCHEDULER_UNAVAILABLE", "Invalid PBS JSON response"
            ) from exc

    async def submit(self, spec: dict, directory: str) -> NativeJob:
        """Submit and obtain scheduler ctime as incarnation evidence."""
        path = await self.stage(spec, directory)
        identity = (await self.native(["qsub", path], mutation=True)).strip()
        if not identity or len(identity) > 256 or any(c.isspace() for c in identity):
            raise MolqError(
                "OUTCOME_UNKNOWN",
                "Unparseable accepted PBS identity",
                outcome="unknown",
            )
        return await self.accepted_identity(identity)

    async def query_many(self, ids: builtins.list[str]) -> dict[str, NativeJob]:
        """Batch extended query; unavailable/unknown-ID output is not terminal."""
        if not ids:
            return {}
        return self._parse(
            await self.native(["qstat", "-x", "-f", "-F", "json", *ids]), "accounting"
        )

    async def list(self) -> builtins.list[NativeJob]:
        """Read PBS queue facts from the current native account."""
        # USER is resolved on the target, not the runtime/client machine.
        text = await self.native(["sh", "-c", 'qstat -f -F json -u "$(id -un)"'])
        return list(self._parse(text, "queue").values())

    async def history(self, ids: builtins.list[str]) -> dict[str, NativeJob]:
        """Read PBS's own retained finished-job accounting."""
        return await self.query_many(ids)

    async def cancel(self, job: NativeJob) -> dict:
        """Acknowledge native cancellation without rewriting JobState."""
        if job.state in TERMINAL:
            return {"outcome": "already_terminal"}
        try:
            await self.native(["qdel", job.native_id], mutation=True)
        except MolqError as exc:
            if exc.kind == "SUBMISSION_REJECTED":
                raise MolqError(
                    "CANCEL_REJECTED", "PBS cancellation rejected", **exc.context
                ) from exc
            raise
        return {"outcome": "accepted"}
