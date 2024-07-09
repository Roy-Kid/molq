from abc import ABC, abstractmethod, ABCMeta
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger("h_submitor")


class JobStatus:
    def __init__(self):
        pass

    def __repr__(self):
        return f"<JobStatus: {self.status}>"


class SubmitRegistry(ABCMeta):

    CLUSTER_REGISTRY: dict[str, "SlurmSubmitor"] = dict()

    def __new__(mcs, name, bases, dct):
        cls = super().__new__(mcs, name, bases, dct)
        if name != "BaseSubmitor":
            logger.debug(f"Registering {cls.cluster_type} adapter")
            SubmitRegistry.CLUSTER_REGISTRY[cls.cluster_type] = cls
        return cls

    def __call__(
        cls, cluster_name: str, cluster_type: str | None = None, *args, **kwargs
    ):
        if cluster_type is None:
            cluster_type = cls.cluster_type
        if cluster_type in SubmitRegistry.CLUSTER_REGISTRY:
            return SubmitRegistry.CLUSTER_REGISTRY[cluster_type].__new__(
                cls, cluster_name, *args, **kwargs
            )
        else:
            raise ValueError(f"Unknown cluster_type: {cluster_type}")


class BaseSubmitor(ABC, metaclass=SubmitRegistry):

    cluster_type: str

    def __init__(self, cluster_name: str):
        self.cluster_name = cluster_name

    def __repr__(self):
        return f"<{self.cluster_type.capitalize()}Adapter: {self.cluster_name}>"

    @abstractmethod
    def submit(
        self,
        cmd: list[str],
        job_name: str,
        n_cores: int,
        memory_max: int | None = None,
        run_time_max: str | int | None = None,
        work_dir: Path | str | None = None,
        account: str | None = None,
        script_name: str | Path = "submit.sh",
        is_monitor: bool = False,
        test_only: bool = False,
        **extra_kwargs,
    ):
        pass

    @abstractmethod
    def remote_submit(self):
        # TODO: use ssh and scp to submit job to remote cluster
        # third-party library: paramiko
        # license: LGPL
        # https://www.paramiko.org/
        pass

    @abstractmethod
    def _gen_script(self, script_name: str, **args):
        pass

    @abstractmethod
    def query(self, job_id: int | None):
        pass

    @abstractmethod
    def watch(self, job_id: int):
        pass

    @abstractmethod
    def monitor(self, job_id: int):
        pass


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
        script_name: str | Path = "run_slurm.sh",
        is_monitor: bool = False,
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

        self._gen_script(Path(script_name), cmd, **slurm_kwargs)

        job_id = self._submit(script_name, test_only)

        if is_monitor:
            self.watch(job_id)

        return job_id

    def _submit(self, script_name, test_only: bool) -> int:
        submit_cmd = ["sbatch", "--parsable"]

        if test_only:
            submit_cmd.append("--test-only")

        submit_cmd.append(script_name)

        try:
            proc = subprocess.run(submit_cmd, capture_output=True)
        except subprocess.CalledProcessError as e:
            raise e

        if test_only:
            # sbatch: Job 3676091 to start at 2024-04-26T20:02:12 using 256 processors on nodes nid001000 in partition main
            job_id = int(proc.stderr.split()[2])
        else:
            job_id = int(proc.stdout)

        return job_id

    def remote_submit(self):
        pass

    def _gen_script(self, script_path: Path, cmd: list[str], **args) -> Path:
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
        cmd = ['squeue', '-j', job_id]
        status = subprocess.run(cmd, capture_output=True)
        if status.returncode != 0:
            raise ValueError(f"Job {job_id} not found.")
        else:
            return JobStatus(status)

    def watch(self):
        pass

    def monitor(self):
        pass
