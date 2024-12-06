import subprocess
from pathlib import Path

from ..submit import BaseSubmitor
from ..monitor import JobStatus


class LocalSubmitor(BaseSubmitor):

    def local_submit(
        self,
        job_name: str,
        cmd: str | list[str],
        script_name: str | Path = "run_local.sh",
        cwd: str | Path = None,
        **kwargs,
    ) -> int:
        
        if isinstance(cmd, str):
            cmd = [cmd]

        if cwd is None:
            script_path = Path(script_name)
        else:
            script_path = Path(cwd) / script_name
        script_path = self._gen_script(script_path, cmd, **kwargs)

        submit_cmd = ["bash", str(script_path.absolute())]
        proc = subprocess.Popen(submit_cmd, cwd=cwd)  # non-blocking

        job_id = int(proc.pid)
        return job_id

    def remote_submit(self):
        pass

    def _gen_script(self, script_path, cmd: list[str], **args) -> Path:
        """generate a temporary script file, and return the path. The file will be deleted after used, or dump for debug.

        Args:
            script_path (Path): path to the script file
            cmd (list[str]): command to be executed

        Returns:
            Path: path to the script file
        """
        with open(script_path, mode="w") as f:
            f.write("#!/bin/bash\n")
            f.write("\n")
            f.write("\n".join(cmd))

        return script_path

    def query(self, job_id: int|None) -> JobStatus:

        cmd = ["ps"]
        query_status = {
            "job_id": "pid=",
            "user": "user=",
            "status": "stat=",
        }
        query_str = [f"-o{v}" for v in query_status.values()]
        cmd.extend(query_str)
        proc = subprocess.run(cmd, capture_output=True)

        # if proc.returncode:
        #     return JobStatus(
        #         job_id=job_id,
        #         status=JobStatus.Status.FINISHED,
        #     )

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

    def validate_config(self, config: dict) -> dict:
        if "job_name" not in config:
            config["job_name"] = "local_job"
        return config

    def cancel(self, job_id: int):
        cmd = ["kill", str(job_id)]
        proc = subprocess.run(cmd, capture_output=True)
        return proc.returncode
