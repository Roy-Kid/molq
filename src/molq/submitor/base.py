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
        return self.status in [
            JobStatus.Status.COMPLETED,
            JobStatus.Status.FAILED,
            JobStatus.Status.FINISHED,
        ]


class BaseSubmitor(ABC):
    """Base class for submitor which is responsible for submitting jobs to different clusters"""

    GLOBAL_JOB_POOL: dict[int, JobStatus] = dict()

    def __init__(self, cluster_name: str, cluster_config: dict = {}):
        self.cluster_name = cluster_name
        self.cluster_config = cluster_config

    def __repr__(self):
        return f"<{self.cluster_name} {self.__class__.__name__}>"

    def submit(self, config: dict):
        config = self.validate_config(config)
        block = config.get("block", False)
        remote = config.get("remote", False)
        if remote:
            job_id = self.remote_submit(**config)
        else:
            job_id = self.local_submit(**config)
        return self.after_submit(job_id, block)

    def after_submit(self, job_id: int, block: bool):
        self.query(job_id=job_id)
        if block:
            self.block_one_until_complete(job_id)
        return job_id

    @abstractmethod
    def local_submit(
        self,
        job_name: str,
        cmd: str | list[str],
        cwd: str | Path = Path.cwd(),
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
    def query(self, job_id: int | None = None) -> dict[int, JobStatus]:
        pass

    @abstractmethod
    def cancel(self, job_id: int):
        pass

    @abstractmethod
    def validate_config(self, config: dict) -> dict:
        return config

    def modify_node(self, node: Callable[..., Any]) -> Callable[..., Any]:
        return node

    @property
    def job_id_list(self):
        return list(self.GLOBAL_JOB_POOL.keys())

    @property
    def jobs(self):
        return self.GLOBAL_JOB_POOL.copy()

    def get_status(self, job_id: int) -> JobStatus:
        return self.GLOBAL_JOB_POOL.get(job_id, None)

    def update_status(self, status: dict[int, JobStatus], verbose: bool = False):
        self.GLOBAL_JOB_POOL = status
        # self.GLOBAL_JOB_POOL = {k: v for k, v in self.GLOBAL_JOB_POOL.items() if not v.is_finish}
        if verbose:
            self.print_status()

    def monitor_all(
        self, interval: int = 60, verbose: bool = True, callback: Callable = None
    ):
        while self.GLOBAL_JOB_POOL:
            self.refresh_status()
            time.sleep(interval)
            if callback:
                callback()

    # backward compat
    def monitor(self, interval: int = 60, verbose: bool = True, callback: Callable = None):
        self.monitor_all(interval=interval, verbose=verbose, callback=callback)

    def block_all_until_complete(self, interval: int = 2, verbose: bool = True):
        while self.GLOBAL_JOB_POOL:
            self.refresh_status()
            time.sleep(interval)

    def block_one_until_complete(
        self, job_id: int, interval: int = 2, verbose: bool = True
    ):
        while True:
            self.refresh_status(verbose=False)
            jobstatus = self.get_status(job_id)
            if jobstatus is None or jobstatus.is_finish:
                break
            time.sleep(interval)

    def get_status_by_name(self, name: str):
        for status in self.jobs.values():
            if name.startswith(status.name):
                return status
        return None

    def refresh_status(self, verbose: bool = True):
        status = self.query()
        self.update_status(status, verbose=verbose)

    def print_status(self):
        """print job status in a nice table

        Args:
            pool (dict[int, JobStatus]): job pool to be printed
        """
        for i, status in enumerate(self.jobs.values(), 1):
            print(f"{status} | {i}/{len(self.GLOBAL_JOB_POOL)} \r", flush=True)
