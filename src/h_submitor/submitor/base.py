from abc import abstractmethod, ABC
import subprocess
from pathlib import Path
import time
import enum

class JobStatus:

    class Status(enum.Enum):
        PENDING = 1
        RUNNING = 2
        COMPLETED = 3
        FAILED = 4

    def __init__(self, job_id: int, partition: str, name: str, user: str, status: str, time: str, nodes: int, nodelist: str):
        self.job_id:int = job_id
        self.partition:str = partition
        self.name:str = name
        self.user:str = user
        self.status:str = status
        self.time:str = time
        self.nodes:int = nodes
        self.nodelist:str = nodelist

    def __repr__(self):
        return f"<Job{self.job_id}: {self.status}>"

def get_submitor(cluster_name: str, cluster_type: str):
    if cluster_type == "slurm":
        return SlurmSubmitor(cluster_name,)
    else:
        raise ValueError(f"Cluster type {cluster_type} not supported.")
    
class BaseSubmitor(ABC):

    cluster_type: str
    registered_clusters = dict()
    queue = dict()  # [job_id, status]

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
        is_block: bool = False,
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
    def query(self, job_id: int | None)->JobStatus:
        pass

    def add_task(self, job_id: int):
        self.queue[job_id] = self.query(job_id)

    def monitor(self, /, job_id: int|list[int]|None = None, interval: int = 60):
        if job_id is None:
            job_id = self.queue.keys()
        elif isinstance(job_id, int):
            job_id = [job_id]

        while job_id:
            for jid in job_id:
                status = self.query(jid)
                print(status)  # TODO: print as a panel
                if status.status == "COMPLETED" or status.status == "FAILED":
                    job_id.remove(jid)
            time.sleep(interval)

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
        script_name: str | Path = "run_slurm.sh",
        is_block: bool = False,
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

        self.gen_script(Path(script_name), cmd, **slurm_kwargs)

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
        elif self.is_local_test:
            job_id = 0
        else:
            job_id = int(proc.stdout)

        self.add_task(job_id)

        if is_block:
            self.monitor(job_id)
        return job_id

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
        cmd = ['squeue', '-j', str(job_id)]
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