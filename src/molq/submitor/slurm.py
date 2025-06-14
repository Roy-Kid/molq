import subprocess
from pathlib import Path

from .base import BaseSubmitor, JobStatus


class SlurmSubmitor(BaseSubmitor):
    """Submit jobs to a SLURM workload manager."""

    def local_submit(
        self,
        job_name: str,
        cmd: list[str],
        n_cores: int,  # --ntasks
        memory_max: int | None = None,  # --mem
        run_time_max: str | int | None = None,  # --time
        partition: str | None = None,  # --partition
        account: str | None = None,  # --account
        # job_deps: str | None = None,
        script_name: str | Path = "run_slurm",
        work_dir: Path = Path.cwd(),  # --chdir
        test_only: bool = False,
        **slurm_kwargs,
    ) -> int:
        submit_config = slurm_kwargs.copy()
        submit_config["--job-name"] = job_name
        submit_config["--ntasks"] = n_cores

        options = {
            "--mem": memory_max,
            "--time": run_time_max,
            "--chdir": str(work_dir.absolute()),
            "--account": account,
            "--partition": partition,
            # "--dependency": job_deps,
        }
        submit_config.update({k: v for k, v in options.items() if v is not None})

        script_path = self._gen_script(Path(work_dir) / script_name, cmd, **submit_config)

        submit_cmd = ["sbatch", str(script_path.absolute()), "--parsable"]

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

    # public helper for tests
    def gen_script(self, script_path: str | Path, cmd: list[str], **kwargs) -> Path:
        return self._gen_script(Path(script_path), cmd, **kwargs)

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
        if "ST" not in status:
            raise ValueError(f"can not find {job_id} status in {status}")
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

