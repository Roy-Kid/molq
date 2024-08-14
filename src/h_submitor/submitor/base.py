import enum
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable


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
    """ factory function to get submitor instance

    :param cluster_name: a unique custom name representing the cluster
    :type cluster_name: str
    :param cluster_type: type of the cluster, e.g. "slurm", "local"
    :type cluster_type: str
    :raises ValueError: if cluster type not supported
    :return: submitor instance
    :rtype: BaseSubmitor
    """
    if cluster_type == "slurm":
        from .slurm import SlurmSubmitor
        return SlurmSubmitor(cluster_name)
    elif cluster_type == "local":
        from .local import LocalSubmitor
        return LocalSubmitor(cluster_name)
    else:
        raise ValueError(f"Cluster type {cluster_type} not supported.")


class Monitor:

    job_pool: dict[int, JobStatus] = dict()

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

    monitor = None

    def __init__(self, cluster_name: str, cluster_config:dict={}):
        self.cluster_name = cluster_name
        self.cluster_config = cluster_config
        self.monitor = Monitor(self.query)

    def __repr__(self):
        return f"<{self.__class__.__name__} for {self.cluster_name}>"

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
    def cancel(self, job_id: int):
        pass

    @abstractmethod
    def validate_config(self, config: dict) -> dict:
        pass

    def modify_node(self, node: Callable[..., Any]) -> Callable[..., Any]:
        return node