import subprocess
from pathlib import Path

from .base import BaseSubmitor, JobStatus


class SlurmSubmitor(BaseSubmitor):

    cluster_type = "slurm"

    def submit(
        self,
        cmd: list[str],
        job_name: str,
        n_cores: int,
        memory_max: int | None = None,
        run_time_max: str | int | None = None,
        work_dir: Path | str | None = None,
        account: str | None = None,
        script_name: str | Path = "run_slurm",
        block: bool = True,
        monitor: int | float = 0,
        test_only: bool = False,
        **slurm_kwargs,
    ) -> int:

        slurm_kwargs["--job-name"] = job_name
        slurm_kwargs["--ntasks"] = n_cores
        if memory_max:
            slurm_kwargs["--mem"] = memory_max
        if run_time_max:
            slurm_kwargs["--time"] = run_time_max
        if work_dir:
            slurm_kwargs["--chdir"] = work_dir
        if account:
            slurm_kwargs["--account"] = account

        script_path = self.gen_script(Path(script_name), cmd, **slurm_kwargs)

        submit_cmd = ["sbatch", "--parsable"]

        if test_only:
            submit_cmd.append("--test-only")

        submit_cmd.append(script_name)

        try:
            proc = subprocess.run(submit_cmd, capture_output=True)
            script_path.unlink()
        except subprocess.CalledProcessError as e:
            raise e

        if test_only:
            # sbatch: Job 3676091 to start at 2024-04-26T20:02:12 using 256 processors on nodes nid001000 in partition main
            job_id = int(proc.stderr.split()[2])
        else:
            job_id = int(proc.stdout)

        return self._base_submit(job_id, monitor, block)

    def remote_submit(self):
        pass

    def gen_script(self, script_path: Path, cmd: list[str], **args) -> Path:
        # assert script_path.exists(), f"Script path {script_path} does not exist."
        script_path = Path(script_path)
        with open(script_path, "w") as f:
            f.write("#!/bin/bash\n")
            for key, value in args.items():
                f.write(f"#SBATCH {key}={value}\n")
            f.write("\n")
            f.write("\n".join(cmd))
        return script_path

    def query(self, job_id: int) -> JobStatus:
        cmd = ["squeue", "-j", str(job_id)]
        proc = subprocess.run(cmd, capture_output=True)
        header, job = proc.stdout.split("\n")
        status = {k: v for k, v in zip(header.split(), job.split())}
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


