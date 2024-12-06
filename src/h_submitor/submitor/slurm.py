import subprocess
from pathlib import Path

from ..submit import BaseSubmitor, JobStatus

class SlurmSubmitor(BaseSubmitor):

    def local_submit(
        self,
        job_name: str,
        cmd: list[str],
        n_cores: int,
        memory_max: int | None = None,
        run_time_max: str | int | None = None,
        cwd: Path = None,
        account: str | None = None,
        script_name: str | Path = "run_slurm",
        test_only: bool = False,
        # job_deps: str | None = None,
        **slurm_kwargs,
    ) -> int:
        submit_config = slurm_kwargs.copy()

        submit_config["--job-name"] = job_name
        submit_config["--ntasks"] = n_cores
        if memory_max:
            submit_config["--mem"] = memory_max
        if run_time_max:
            submit_config["--time"] = run_time_max
        if cwd:
            submit_config["--chdir"] = cwd
        if account:
            submit_config["--account"] = account
        # if job_deps:
        #     self.refresh_status()
            
        #     if isinstance(job_deps, str):
        #         job_status = self.get_status_by_name(job_deps)
        #         if not job_status:
        #             raise ValueError(f"job {job_deps} not found in {[j.name for j in self.monitor.job_pool.values()]}")
        #         submit_config["--dependency"] = f"afterok:{job_status.job_id}"

            # if isinstance(job_deps, list):
            #     submit_config["--dependency"] = "afterok:" + ":".join(
            #         map(str, job_deps)
            #     )
            # elif isinstance(job_deps, dict):
            #     condition = job_deps.pop("condition", ",")  # default to AND
            #     submit_config["--dependency"] = condition.join(
            #         f"{k}:{':'.join(map(str, [job_mapping[j] for j in v]))}"
            #         for k, v in job_deps.items()
            #     )

        script_path = self._gen_script(Path(cwd) / script_name, cmd, **submit_config)

        submit_cmd = ["sbatch", str(script_path.absolute), "--parsable"]

        if test_only:
            submit_cmd.append("--test-only")

        submit_cmd.append(script_name)

        try:
            proc = subprocess.run(submit_cmd, capture_output=True)
            # script_path.unlink()
        except subprocess.CalledProcessError as e:
            raise e

        if test_only:
            # example output:
            # sbatch: Job 3676091 to start at 2024-04-26T20:02:12 using 256 processors on nodes nid001000 in partition main
            job_id = int(proc.stderr.split()[2])
        else:
            job_id = int(proc.stdout)

        return job_id

    def remote_submit(self):
        pass

    def _gen_script(self, script_path: Path, cmd: list[str], **kwargs) -> Path:
        assert script_path.parent.exists(), f"{script_path.parent} does not exist"
        with open(script_path, "w") as f:
            f.write("#!/bin/bash\n")
            for key, value in kwargs.items():
                f.write(f"#SBATCH {key}={value}\n")
            f.write("\n")
            f.write("\n".join(cmd))
        return script_path

    def query(self, job_id: int) -> JobStatus:
        cmd = ["squeue", "-j", str(job_id)]
        proc = subprocess.run(cmd, capture_output=True)
        try:
            out = proc.stdout.decode()
            header, job = out.split("\n")[:2]
        except Exception as e:
            raise ValueError(f"can not find {job_id} in {out}") from e
        status = {k: v for k, v in zip(header.split(), job.split())}
        if 'ST' not in status:
            raise ValueError(f'can not find {job_id} status in {status}')
        if status["ST"] == "R":
            enum_status = "RUNNING"
        elif status["ST"] == "PD":
            enum_status = "PENDING"
        elif status["ST"] == "CD":
            enum_status = "COMPLETED"
        else:
            enum_status = "FAILED"
        return JobStatus(
            job_id=int(status["JOBID"]),
            partition=status["PARTITION"],
            name=status["NAME"],
            user=status["USER"],
            status=JobStatus.Status[enum_status],
            time=status["TIME"],
            nodes=int(status["NODES"]),
            nodelist=status["NODELIST(REASON)"],
        )

    def validate_config(self, config: dict) -> dict:
        return super().validate_config(config)

    def cancel(self, job_id: int):
        cmd = ["scancel", str(job_id)]
        proc = subprocess.run(cmd, capture_output=True)
        return proc.returncode
