# pragma: no cover - CLI interaction is hard to test fully
import subprocess
from pathlib import Path

from .base import BaseSubmitor, JobStatus


class LocalSubmitor(BaseSubmitor):
    """Execute jobs on the current machine using ``bash``."""

    def local_submit(
        self,
        job_name: str,
        cmd: str | list[str],
        cwd: str | Path | None = None,
        script_name: str | Path = "run_local.sh",
        conda_env: str | None = None,
        quiet: bool = False,
        block: bool = False,
        # Unified ResourceSpec parameters (mostly ignored for local execution)
        cpu_count: int | None = None,
        memory: str | None = None,
        time_limit: str | None = None,
        queue: str | None = None,
        gpu_count: int | None = None,
        gpu_type: str | None = None,
        email: str | None = None,
        email_events: list | None = None,
        priority: str | None = None,
        # Aliases for compatibility
        workdir: str | Path | None = None,
        **kwargs,
    ) -> int:
        """Run ``cmd`` locally by generating and executing a shell script."""

        if isinstance(cmd, str):
            cmd = [cmd]

        # Handle workdir alias
        if workdir is not None:
            cwd = workdir

        if cwd is None:
            script_path = Path(script_name)
        else:
            cwd = Path(cwd)
            if not cwd.exists():
                cwd.mkdir(parents=True, exist_ok=True)
            script_path = cwd / script_name
        script_path = self._gen_script(script_path, cmd, conda_env, **kwargs)

        submit_cmd = ["bash", str(script_path.absolute())]
        spparams = {}
        if quiet:
            spparams["stdin"] = subprocess.DEVNULL
            spparams["stdout"] = subprocess.DEVNULL
            spparams["stderr"] = subprocess.DEVNULL

        proc = subprocess.Popen(
            submit_cmd,
            cwd=cwd,
            **spparams,
        )  # non-blocking
        if block:
            proc.wait()
            if proc.returncode != 0:
                raise RuntimeError(f"Job {job_name} failed with return code {proc.returncode}")

        job_id = int(proc.pid)
        return job_id

    def remote_submit(self):
        """Submit a job to a remote machine (unimplemented)."""
        pass  # pragma: no cover

    def _gen_script(self, script_path, cmd: list[str], conda_env, **args) -> Path:
        """generate a temporary script file, and return the path. The file will be deleted after used, or dump for debug.

        Args:
            script_path (Path): path to the script file
            cmd (list[str]): command to be executed
            conda_env (str): conda environment to be activated

        Returns:
            Path: path to the script file
        """
        with open(script_path, mode="w") as f:
            f.write("#!/bin/bash\n")

            if conda_env:
                f.write(f"source $(conda info --base)/etc/profile.d/conda.sh\n")
                f.write(f"conda activate {conda_env}\n")

            f.write("\n")
            f.write(" ".join(cmd))

        return script_path

    def query(self, job_id: int | None = None) -> dict[int, JobStatus]:  # pragma: no cover
        """Return a mapping of job IDs to statuses using ``ps``."""

        cmd = [
            "ps",
            "--no-headers",
        ]
        if job_id:
            cmd.extend(["-p", str(job_id)])
        query_status = {
            "job_id": "pid",
            "user": "user",
            "status": "stat",
        }
        query_str = ",".join(query_status.values())
        cmd.extend(["-o", query_str])
        proc = subprocess.run(cmd, capture_output=True)
        # WARNING: will return all jobs in this computer
        if proc.stderr:
            raise RuntimeError(proc.stderr.decode())

        out = proc.stdout.decode().strip()
        status = {}
        if out:
            lines = [line.split() for line in out.split("\n")]

            status_map = {
                "S": JobStatus.Status.RUNNING,
                "R": JobStatus.Status.RUNNING,
                "D": JobStatus.Status.PENDING,
                "Z": JobStatus.Status.COMPLETED,
            }
            status = {
                int(line[0]): JobStatus(int(line[0]), status_map[line[2][0]])
                for line in lines
            }

        return status

    def validate_config(self, config: dict) -> dict:
        """Fill in defaults for missing configuration values."""
        if "job_name" not in config:
            config["job_name"] = "local_job"
        return config

    def cancel(self, job_id: int) -> None:
        """Terminate a running process."""
        cmd = ["kill", str(job_id)]
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to cancel job {job_id}: {proc.stderr.decode()}")

