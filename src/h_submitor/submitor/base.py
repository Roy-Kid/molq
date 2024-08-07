from abc import abstractmethod, ABC
import subprocess
from pathlib import Path
import time
import enum
from typing import Callable
import random

class JobStatus:

    class Status(enum.Enum):
        PENDING = 1
        RUNNING = 2
        COMPLETED = 3
        FAILED = 4

    def __init__(self, job_id: int, status: Status, name: str = "", **others: str):
        self.name: str = name
        self.job_id: int = job_id
        self.status: str = status

        self.others: dict[str] = others

    def __repr__(self):
        return f"<Job {self.name}({self.job_id}): {self.status}>"


def get_submitor(cluster_name: str, cluster_type: str):
    if cluster_type == "slurm":
        return SlurmSubmitor(
            cluster_name,
        )
    elif cluster_type == "local":
        return LocalSubmitor(
            cluster_name,
        )
    else:
        raise ValueError(f"Cluster type {cluster_type} not supported.")


class Monitor:

    job_pool: dict[int, JobStatus] = dict()

    def __init__(
        self, query_fn: Callable[[int], JobStatus], interval: int | float | bool = 60
    ):
        self.query_fn = query_fn
        self.interval = float(interval)

    @property
    def job_id_list(self):
        return list(self.job_pool.keys())
    
    @property
    def jobs(self):
        return self.job_pool.copy()

    def monitor(self, job_id: int | list[int]):

        if isinstance(job_id, int):
            job_id = [job_id]

        self.job_pool.update({id_: self.query_fn(id_) for id_ in job_id})

        while self.job_pool:
            for job_id in self.job_id_list:
                job_status = self.query_fn(job_id)
                if (
                    job_status.status == JobStatus.Status.COMPLETED
                    or job_status.status == JobStatus.Status.FAILED
                ):
                    self.job_pool.pop(job_id)
                else:
                    self.job_pool[job_id] = job_status
                time.sleep(self.interval)

            self.print_status()

    def print_status(self):
        """print job status in a nice table

        Args:
            pool (dict[int, JobStatus]): job pool to be printed
        """
        for i, status in enumerate(self.jobs.values(), 1):
            print(f"{status} | {i}/{len(self.job_pool)}")


class BaseSubmitor(ABC):

    cluster_type: str
    registered_clusters = dict()
    queue = dict()  # [job_id, status]
    monitor = None

    def __init__(self, cluster_name: str):
        self.cluster_name = cluster_name
        self.registered_clusters[cluster_name] = self

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
        monitor: int | bool = 0,
        test_only: bool = False,
        **extra_kwargs,
    ):
        pass

    def _base_submit(
        self,
        job_id: int,
        monitor: int = 0,
    ) -> int:
        if monitor:
            if self.monitor is None:
                self.monitor = Monitor(self.query, monitor)
            self.monitor.monitor(job_id)

        return job_id

    @abstractmethod
    def remote_submit(self):
        # TODO: use ssh and scp to submit job to remote cluster
        # third-party library: paramiko
        # license: LGPL
        # https://www.paramiko.org/
        pass

    @abstractmethod
    def query(self, job_id: int | None) -> JobStatus:
        pass

    def add_task(self, job_id: int):
        self.queue[job_id] = self.query(job_id)

    @abstractmethod
    def gen_script(self, script_path: Path, cmd: list[str], **args) -> Path:
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
        script_name: str | Path = "run_slurm",
        monitor: bool = False,
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

        self.add_task(job_id)

        return self._base_submit(job_id)

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
        script_name: str | Path = "run_local",
        monitor: int | float | bool = False,
        test_only: bool = False,
        **slurm_kwargs,
    ) -> int:

        script_path = self.gen_script(Path(script_name), cmd, **slurm_kwargs)

        submit_cmd = ["bash", script_path]

        proc = subprocess.Popen(submit_cmd)

        job_id = int(proc.pid)

        self.add_task(job_id)
        script_path.unlink()
        return self._base_submit(job_id, monitor)

    def remote_submit(self):
        pass

    def gen_script(self, script_path: Path, cmd: list[str], **args) -> Path:
        # assert script_path.exists(), f"Script path {script_path} does not exist."
        path = Path(script_path).parent
        name = Path(script_path).name + format(random.randint(0, 255), '02x') + ".sh"
        script_path = path / name
        with open(script_path, "w") as f:
            f.write("#!/bin/bash\n")
            f.write("\n")
            f.write("\n".join(cmd))
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
        proc = subprocess.run(cmd, capture_output=True, check=True)
        if proc.stderr.decode().strip():
            raise SystemError(f"Job {job_id} does not exist.")

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
