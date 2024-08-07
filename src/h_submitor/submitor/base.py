from abc import abstractmethod, ABC
import subprocess
from pathlib import Path
import time
import enum
from typing import Callable
import tempfile

class JobStatus:

    class Status(enum.Enum):
        PENDING = 1
        RUNNING = 2
        COMPLETED = 3
        FAILED = 4
        FINISHED = 5

    def __init__(self, job_id: int, status: Status, name: str = "", **others: str):
        self.name: str = name
        self.job_id: int = job_id
        self.status: str = status

        self.others: dict[str] = others

    def __repr__(self):
        return f"<Job {self.name}({self.job_id}): {self.status}>"
    
    @property
    def is_finish(self) -> bool:
        return self.status in [JobStatus.Status.COMPLETED, JobStatus.Status.FAILED, JobStatus.Status.FINISHED]


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

    def __new__(cls, query_fn: Callable[[int], JobStatus]):
        
        # check if in multiprocessing environment and its master
        # cls.job_pool = multiprocesing.Manager().dict()
        # Error: 
        """Traceback (most recent call last):
  File "/home/jicli594/work/Hamilton-HPC-Orchestra/example/run_multi_proc.py", line 19, in <module>
    dr.execute(["reducer"], inputs={"seconds": [3, 6]})
  File "/home/jicli594/miniconda3/envs/work/lib/python3.10/site-packages/hamilton/driver.py", line 556, in execute
    outputs = self.raw_execute(_final_vars, overrides, display_graph, inputs=inputs)
  File "/home/jicli594/miniconda3/envs/work/lib/python3.10/site-packages/hamilton/driver.py", line 674, in raw_execute
    results = self.graph_executor.execute(
  File "/home/jicli594/miniconda3/envs/work/lib/python3.10/site-packages/hamilton/driver.py", line 232, in execute
    executors.run_graph_to_completion(execution_state, self.execution_manager)
  File "/home/jicli594/miniconda3/envs/work/lib/python3.10/site-packages/hamilton/execution/executors.py", line 374, in run_graph_to_completion
    while not GraphState.is_terminal(execution_state.get_graph_state()):
  File "/home/jicli594/miniconda3/envs/work/lib/python3.10/site-packages/hamilton/execution/state.py", line 441, in get_graph_state
    [state == TaskState.INITIALIZED for state in self.task_states.values()]
  File "/home/jicli594/miniconda3/envs/work/lib/python3.10/site-packages/hamilton/execution/state.py", line 441, in <listcomp>
    [state == TaskState.INITIALIZED for state in self.task_states.values()]
KeyboardInterrupt
        """
        return super().__new__(cls)

    def __init__(
        self, query_fn: Callable[[int], JobStatus]
    ):
        self.query_fn = query_fn

    @property
    def job_id_list(self):
        return list(self.job_pool.keys())

    @property
    def jobs(self):
        return self.job_pool.copy()

    def add_job(self, job_id: int):
        self.job_pool[job_id] = self.query_fn(job_id)

    def add_jobs(self, job_ids: list[int]):
        for id_ in job_ids:
            self.job_pool[id_] = self.query_fn(id_)

    def monitor_all(self, interval: int = 60):
        while self.job_pool:
            for job_id in self.job_id_list:
                job_status = self.query_fn(job_id)
                if job_status.is_finish:
                    self.job_pool.pop(job_id)
                else:
                    self.job_pool[job_id] = job_status
                time.sleep(interval)

            self.print_status()

    def block_until_complete(self, job_id: int, interval: int = 60):
        while True:
            job_status = self.query_fn(job_id)
            print(job_status)
            if job_status.is_finish:
                if job_id in self.job_pool:
                    self.job_pool.pop(job_id)
                break
            time.sleep(interval)

    def print_status(self):
        """print job status in a nice table

        Args:
            pool (dict[int, JobStatus]): job pool to be printed
        """
        for i, status in enumerate(self.jobs.values(), 1):
            print(f"{status} | {i}/{len(self.job_pool)}", flush=True)


class BaseSubmitor(ABC):

    cluster_type: str
    registered_clusters = dict()
    monitor = None

    def __init__(self, cluster_name: str):
        self.cluster_name = cluster_name
        self.registered_clusters[cluster_name] = self
        self.monitor = Monitor(self.query)

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
        block: bool | int | float = False,
        test_only: bool = False,
        **extra_kwargs,
    ):
        pass

    def _base_submit(
        self,
        job_id: int,
        monitor: bool = 0,
        block: int | float | bool = True,
    ) -> int:
        """common submit process for all submitors

        Args:
            job_id (int): job id
            block (bool, optional): if block here until complete. Defaults to False.
            monitor (bool, optional): 0 if not add job to monitor list, else as an intervel(in second) for query. Defaults to 0.

        Returns:
            int: job_id
        """
        if monitor:
            self.monitor.add_job(job_id)

        if block:
            self.monitor.block_until_complete(job_id, float(block))

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
