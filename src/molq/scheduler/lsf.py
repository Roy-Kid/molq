"""LSF directives and native accounting; no raw flags in public Job schema."""

from __future__ import annotations

import builtins
import json
import re
import shlex

from molq.errors import MolqError
from molq.scheduler.base import TERMINAL, NativeJob, _SchedulerMethods
from molq.scheduler.execution import render_execution

SUBMIT_ID = re.compile(r"Job <(\d+)>")
DEPENDENCIES = {
    "after": "ended",
    "after_success": "done",
    "after_failure": "exit",
    "after_started": "started",
}


class LSFScheduler(_SchedulerMethods):
    """Finite bsub/bjobs/bkill operations through the configured Transport."""

    def validate(self, spec: dict) -> None:
        """Reject site-dependent layouts/resources without an exact configured map."""
        super().validate(spec)
        r, s = spec["resources"], spec["scheduling"]
        for unit in spec["execution"]["units"]:
            launch = unit.get("launch", {})
            if (
                launch.get("ranks", 1) > r.get("tasks", 1)
                or launch.get("threads", 1) != 1
            ):
                raise MolqError(
                    "EXECUTION_RESOURCE_CONFLICT",
                    "MPI launch exceeds the LSF allocation layout",
                )
        if r.get("nodes", 1) != 1 or r.get("cpus_per_task", 1) != 1:
            self.unsupported(
                "LSF mapping currently requires a single-node single-thread task layout"
            )
        if "memory_bytes" in r or r.get("accelerators"):
            self.unsupported(
                "LSF memory/GPU/MPS allocation semantics require an explicit site mapping"
            )
        if any(k in s for k in ("qos", "reservation")):
            self.unsupported("No exact LSF mapping for these scheduling intents")
        if len(spec["execution"]["units"]) > 1 and "tasks" not in r:
            raise MolqError(
                "RESOURCE_REQUEST_INVALID",
                "Multi-unit batch execution requires explicit tasks",
            )

    def render(self, spec: dict, directory: str) -> str:
        """Render a formal LSF request without inventing unsupported resources."""
        self.validate(spec)
        r, s = spec["resources"], spec["scheduling"]
        directives = [
            f"-cwd {shlex.quote(directory)}",
            f"-o {shlex.quote(directory + '/stdout')}",
            f"-e {shlex.quote(directory + '/stderr')}",
            f"-n {r.get('tasks', 1)}",
            '-R "span[hosts=1]"',
        ]
        if seconds := r.get("time_limit_seconds"):
            # LSF wall time is minute-granular; reserve at least requested time.
            minutes = (seconds + 59) // 60
            directives.append(f"-W {minutes // 60}:{minutes % 60:02}")
        for field, flag in [
            ("name", "J"),
            ("partition", "q"),
            ("account", "P"),
            ("priority", "sp"),
        ]:
            if field in s:
                directives.append(f"-{flag} {s[field]}")
        if s.get("exclusive"):
            directives.append("-x")
        if edges := s.get("dependencies"):
            expr = " && ".join(
                f"{DEPENDENCIES[e['condition']]}({e['ref']['native_id']})"
                for e in edges
            )
            directives.append("-w " + shlex.quote(expr))
        return (
            "#!/usr/bin/env bash\n"
            + "\n".join("#BSUB " + d for d in directives)
            + "\n"
            + render_execution(spec, self.launch)
        )

    @staticmethod
    def _parse(text: str) -> dict[str, NativeJob]:
        try:
            rows = json.loads(text)["RECORDS"]
            jobs = {}
            for row in rows:
                if "ERROR" in row:
                    raise ValueError("LSF reported a partial query failure")
                identity = str(row["JOBID"])
                raw = row["STAT"]
                state = {
                    "PEND": "queued",
                    "WAIT": "queued",
                    "RUN": "running",
                    "PSUSP": "running",
                    "USUSP": "running",
                    "SSUSP": "running",
                    "DONE": "succeeded",
                    "EXIT": "failed",
                    "ZOMBI": "unknown",
                    "UNKWN": "unknown",
                }.get(raw, "unknown")
                code = row.get("EXIT_CODE")
                output = row.get("OUTPUT_FILE")
                error = row.get("ERROR_FILE")
                workdir = row.get("EXEC_CWD")
                if not workdir or workdir == "-":
                    workdir = (
                        output.rsplit("/", 1)[0]
                        if output and output.startswith("/")
                        else None
                    )
                submitted = str(row.get("SUBMIT_TIME", ""))
                incarnation = (
                    submitted + "|" + output
                    if submitted and output and output != "-"
                    else submitted
                )
                jobs[identity] = NativeJob(
                    identity,
                    incarnation,
                    state,
                    "accounting",
                    raw,
                    int(code) if str(code).isdigit() else None,
                    workdir,
                    row.get("JOB_NAME"),
                    output if output and output != "-" else None,
                    error if error and error != "-" else None,
                )
            return jobs
        except (ValueError, KeyError, TypeError) as exc:
            raise MolqError(
                "SCHEDULER_UNAVAILABLE", "Invalid/partial LSF query response"
            ) from exc

    async def submit(self, spec: dict, directory: str) -> NativeJob:
        """Submit script over native stdin and verify allocation identity."""
        await self.stage(spec, directory)
        text = await self.native(
            ["bsub"], mutation=True, input=self.render(spec, directory).encode()
        )
        match = SUBMIT_ID.search(text)
        if not match:
            raise MolqError(
                "OUTCOME_UNKNOWN",
                "Unparseable accepted LSF identity",
                outcome="unknown",
            )
        identity = match[1]
        return await self.accepted_identity(identity)

    async def query_many(self, ids: builtins.list[str]) -> dict[str, NativeJob]:
        """Query current and LSF-retained recent history in one batch."""
        if not ids:
            return {}
        text = await self.native(
            [
                "bjobs",
                "-a",
                "-json",
                "-o",
                "jobid stat submit_time exec_cwd output_file error_file job_name exit_code",
                *ids,
            ]
        )
        return self._parse(text)

    async def list(self) -> builtins.list[NativeJob]:
        """Read native account queue facts."""
        return list(
            self._parse(
                await self.native(
                    [
                        "bjobs",
                        "-json",
                        "-o",
                        "jobid stat submit_time exec_cwd output_file error_file job_name exit_code",
                    ]
                )
            ).values()
        )

    async def history(self, ids: builtins.list[str]) -> dict[str, NativeJob]:
        """Read the native recent-history window, not a molq archive."""
        return await self.query_many(ids)

    async def cancel(self, job: NativeJob) -> dict:
        """Return only bkill acceptance; later queries establish execution truth."""
        if job.state in TERMINAL:
            return {"outcome": "already_terminal"}
        try:
            await self.native(["bkill", job.native_id], mutation=True)
        except MolqError as exc:
            if exc.kind == "SUBMISSION_REJECTED":
                raise MolqError(
                    "CANCEL_REJECTED", "LSF cancellation rejected", **exc.context
                ) from exc
            raise
        return {"outcome": "accepted"}
