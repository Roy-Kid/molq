import subprocess
from pathlib import Path

from ..submit import BaseSubmitor, JobStatus


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
            cwd = Path(cwd)
            if not cwd.exists():
                cwd.mkdir(parents=True, exist_ok=True)
            script_path = cwd / script_name
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

    def query(self, job_id: int|None = None) -> dict[int, JobStatus]:

        cmd = ["ps", "--no-headers"]
        query_status = {
            "job_id": "pid",
            "user": "user",
            "status": "stat",
        }
        query_str = ','.join(query_status.values())
        cmd.extend(["-o", query_str])
        if job_id:
            cmd.extend(["-p", str(job_id)])
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
            status = {int(line[0]): JobStatus(int(line[0]), status_map[line[2][0]]) for line in lines}

        return status

    def validate_config(self, config: dict) -> dict:
        if "job_name" not in config:
            config["job_name"] = "local_job"
        return config

    def cancel(self, job_id: int):
        cmd = ["kill", str(job_id)]
        proc = subprocess.run(cmd, capture_output=True)
        return proc.returncode
