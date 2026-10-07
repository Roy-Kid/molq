"""Shell execution truth is original target launch/exit evidence, not a DB."""

from __future__ import annotations

import builtins
import posixpath
import shlex

from molq.errors import MolqError
from molq.scheduler.base import NativeJob, _SchedulerMethods
from molq.scheduler.execution import render_execution

q = shlex.quote


class ShellScheduler(_SchedulerMethods):
    """Detached Bash allocations with identity-checked process-group cancellation."""

    def validate(self, spec: dict) -> None:
        """Reject formal batch resource/scheduling requests on a Shell target."""
        if spec.get("resources") or spec.get("scheduling"):
            self.unsupported(
                "Shell targets do not provide formal allocation resources or scheduling"
            )
        super().validate(spec)

    def render(self, spec: dict, directory: str) -> str:
        """Write atomic original execution receipts from the target wrapper."""
        d = q(directory)
        return f"""#!/usr/bin/env bash
umask 077
receipt_dir={d}
start=$(LC_ALL=C ps -p $$ -o lstart=)
printf '%s\\n%s\\n' "$$" "$start" > "$receipt_dir/launch.tmp"
mv "$receipt_dir/launch.tmp" "$receipt_dir/launch"
finish() {{
  code=$?
  trap - EXIT
  printf '%s\\n' "$code" > "$receipt_dir/exit.tmp"
  mv "$receipt_dir/exit.tmp" "$receipt_dir/exit"
}}
trap finish EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
cd -- "$receipt_dir" || exit 126
""" + render_execution(spec, self.launch)

    async def submit(self, spec: dict, directory: str) -> NativeJob:
        """Detach the target process group; return only after launch evidence."""
        path = await self.stage(spec, directory)
        script = f"set -m; nohup bash {q(path)} </dev/null >{q(directory + '/stdout')} 2>{q(directory + '/stderr')} &"
        await self.native(["bash", "-c", script], mutation=True)
        identity = posixpath.basename(directory)
        import asyncio

        try:
            for _ in range(40):
                jobs = await self.query_many([identity])
                if identity in jobs:
                    return jobs[identity]
                await asyncio.sleep(0.025)
        except MolqError as exc:
            raise MolqError(
                "OUTCOME_UNKNOWN",
                "Shell accepted launch but evidence query failed",
                outcome="unknown",
                native_id=identity,
            ) from exc
        raise MolqError(
            "OUTCOME_UNKNOWN",
            "Shell launch evidence unavailable",
            outcome="unknown",
            native_id=identity,
        )

    def _directory(self, identity: str) -> str:
        return posixpath.join(self.cluster["target_root"], identity)

    async def query_many(self, ids: builtins.list[str]) -> dict[str, NativeJob]:
        """Read a batch of original receipts; missing evidence stays unknown."""
        if not ids:
            return {}
        commands = []
        for identity in ids:
            d = q(self._directory(identity))
            commands.append(f"""d={d}; if [ -f "$d/launch" ]; then
read -r pid < "$d/launch"
start=$(sed -n '2p' "$d/launch")
state=unknown; code=''
if [ -f "$d/exit" ]; then
  read -r code < "$d/exit"
  state=failed; [ "$code" = 0 ] && state=succeeded
  if [ -f "$d/cancel_requested" ] && {{ [ "$code" = 143 ] || [ "$code" = 130 ]; }}; then state=cancelled; fi
elif [ "$(LC_ALL=C ps -p "$pid" -o lstart= 2>/dev/null)" = "$start" ]; then state=running
fi
printf '%s|%s|%s|%s|%s\\n' {q(identity)} "$pid" "$start" "$state" "$code"
fi""")
        text = await self.native(["bash", "-c", "\n".join(commands)])
        jobs = {}
        for line in text.splitlines():
            identity, pid, start, state, code = line.split("|")
            if not pid.isdigit() or not start.strip():
                raise MolqError("SCHEDULER_UNAVAILABLE", "Invalid Shell launch receipt")
            jobs[identity] = NativeJob(
                identity,
                f"{pid}:{start}",
                state,
                "shell_receipt",
                state,
                int(code) if code else None,
                self._directory(identity),
            )
        return jobs

    async def list(self) -> builtins.list[NativeJob]:
        """Enumerate bounded Shell receipts, without inventing a JobStore."""
        text = await self.native(
            [
                "bash",
                "-c",
                f'for d in {q(self.cluster["target_root"])}/*; do [ -f "$d/launch" ] && [ ! -f "$d/exit" ] && basename "$d"; done; true',
            ]
        )
        ids = text.splitlines()
        if len(ids) > 1024:
            raise MolqError(
                "PARTIAL_FAILURE",
                "Shell receipt scope exceeds 1024; query explicit refs",
            )
        return list((await self.query_many(ids)).values())

    async def history(self, ids: builtins.list[str]) -> dict[str, NativeJob]:
        """Read original receipts for explicitly selected executions."""
        return await self.query_many(ids)

    async def cancel(self, job: NativeJob) -> dict:
        """Verify PID/start identity before signalling its detached process group."""
        if job.state in {"succeeded", "failed", "cancelled", "timed_out"}:
            return {"outcome": "already_terminal"}
        d = q(self._directory(job.native_id))
        script = f"""d={d}
[ -f "$d/launch" ] || exit 2
read -r pid < "$d/launch"
start=$(sed -n '2p' "$d/launch")
[ "$(LC_ALL=C ps -p "$pid" -o lstart= 2>/dev/null)" = "$start" ] || exit 3
printf 'requested\\n' > "$d/cancel_requested"
kill -TERM -- -"$pid"
"""
        try:
            await self.native(["bash", "-c", script], mutation=True)
        except MolqError as exc:
            if exc.kind == "SUBMISSION_REJECTED":
                raise MolqError(
                    "CANCEL_REJECTED", "Target cancellation was rejected", **exc.context
                ) from exc
            raise
        return {"outcome": "accepted"}
