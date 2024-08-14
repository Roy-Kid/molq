import subprocess
import tempfile
from pathlib import Path

from .base import BaseSubmitor, JobStatus


class LocalSubmitor(BaseSubmitor):

    cluster_type = "local"

    def submit(
        self,
        cmd: list[str],
        job_name: str,
        n_cores: int = 0,
        memory_max: int | None = None,
        run_time_max: str | int | None = None,
        work_dir: Path | str | None = None,
        account: str | None = None,
        script_path: str | Path | None = None,
        monitor: bool = True,
        block: int | float | bool = False,
        test_only: bool = False,
        **kwargs,
    ) -> int:

        script_path = self.gen_script(script_path, cmd, **kwargs)

        submit_cmd = ["bash", script_path]

        proc = subprocess.Popen(submit_cmd)

        job_id = int(proc.pid)

        return self._base_submit(job_id, monitor, block)

    def remote_submit(self):
        pass

    def gen_script(self, script_path: Path|str|None, cmd: list[str], **args) -> Path:
        """generate a temporary script file, and return the path. The file will be deleted after used, or dump for debug.

        Args:
            script_path (Path): path to the script file
            cmd (list[str]): command to be executed

        Returns:
            Path: path to the script file
        """
        if script_path is None:
            pass
        elif isinstance(script_path, str):
            script_path = Path(script_path)
            
        with tempfile.NamedTemporaryFile(delete=False, dir=script_path, mode='w') as f:
            f.write("#!/bin/bash\n")
            f.write("\n")
            f.write("\n".join(cmd))

        script_path = Path(f.name)

        return script_path

    def query(self, job_id: int) -> JobStatus:
        cmd = ["ps", "-p", str(job_id)]
        query_status = {
            "job_id": "pid=",
            "user": "user=",
            "status": "stat=",
        }
        query_str = [f"-o{v}" for v in query_status.values()]
        cmd.extend(query_str)
        proc = subprocess.run(cmd, capture_output=True)

        if proc.returncode:
            return JobStatus(
                job_id=job_id,
                status=JobStatus.Status.FINISHED,
            )

        out = proc.stdout.decode().strip()
        status = {k: v for k, v in zip(query_status.keys(), out.split())}

        status_map = {
            "S": JobStatus.Status.RUNNING,
            "R": JobStatus.Status.RUNNING,
            "D": JobStatus.Status.PENDING,
            "Z": JobStatus.Status.COMPLETED,
        }
        status["status"] = status_map[status["status"][0]]

        return JobStatus(**status)
