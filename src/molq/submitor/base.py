"""Submitter base classes used by ``molq.submit`` decorators."""

import enum
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union, List


class JobStatus:
    """Lightweight representation of a job's state."""

    class Status(enum.Enum):
        PENDING = 1
        RUNNING = 2
        COMPLETED = 3
        FAILED = 4
        FINISHED = 5

    def __init__(self, job_id: int, status: Status, name: str = "", **others: str):
        """Create a :class:`JobStatus` instance.

        Parameters
        ----------
        job_id:
            Identifier returned by the scheduler.
        status:
            Initial job state.
        name:
            Optional human readable job name.
        others:
            Additional status fields.
        """
        self.name: str = name
        self.job_id: int = job_id
        self.status: JobStatus.Status = status

        self.others: dict[str, str] = others

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
    """Abstract interface for cluster-specific submitters."""

    GLOBAL_JOB_POOL: dict[int, JobStatus] = dict()

    def __init__(self, cluster_name: str, cluster_config: dict = {}):
        """Initialize a submitter.

        Parameters
        ----------
        cluster_name:
            Name identifying the cluster.
        cluster_config:
            Arbitrary configuration passed to the concrete implementation.
        """
        self.cluster_name = cluster_name
        self.cluster_config = cluster_config

    def __repr__(self):
        """Return a concise textual representation."""
        return f"<{self.cluster_name} {self.__class__.__name__}>"

    def submit(self, config: dict):
        """Submit a job described by ``config``.

        The configuration dictionary is first validated, then dispatched to the
        local or remote submission routines.
        """
        config = self.validate_config(config)
        block = config.get("block", False)
        remote = config.get("remote", False)
        if remote:
            job_id = self.remote_submit(**config)
        else:
            job_id = self.local_submit(**config)
        return self.after_submit(job_id, block)

    def after_submit(self, job_id: int, block: bool):
        """Handle a newly submitted job."""
        self.query(job_id=job_id)
        if block:
            self.block_one_until_complete(job_id)
        return job_id

    @abstractmethod
    def local_submit(
        self,
        job_name: str,
        cmd: str | list[str],
        cwd: str | Path | None = None,
        block: bool = False,
        **resource_kwargs,
    ) -> int:
        """Submit a job to the local execution environment.
        
        Args:
            job_name: Name for the job
            cmd: Command to execute
            cwd: Working directory (optional)
            block: Whether to wait for completion
            **resource_kwargs: Additional resource specifications
            
        Returns:
            Job identifier
        """
        pass  # pragma: no cover

    @abstractmethod
    def remote_submit(
        self,
        job_name: str,
        cmd: str | list[str],
        cwd: str | Path | None = None,
        block: bool = False,
        **resource_kwargs,
    ) -> int:
        """Submit a job to a remote cluster.
        
        Args:
            job_name: Name for the job
            cmd: Command to execute
            cwd: Working directory (optional)
            block: Whether to wait for completion
            **resource_kwargs: Additional resource specifications
            
        Returns:
            Job identifier
        """
        pass  # pragma: no cover

    @abstractmethod
    def query(self, job_id: int | None = None) -> dict[int, JobStatus]:
        """Query the status of ``job_id`` or all jobs."""
        pass  # pragma: no cover

    @abstractmethod
    def cancel(self, job_id: int) -> None:
        """Cancel a running job."""
        pass

    def validate_config(self, config: dict) -> dict:
        """Validate and normalize the user provided configuration."""
        # Provide default validation that can be overridden
        required_fields = ['job_name', 'cmd']
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Required field '{field}' missing from job configuration")
        
        # Normalize cmd to list format
        if isinstance(config['cmd'], str):
            config['cmd'] = [config['cmd']]
            
        return config

    def prepare_resource_spec(self, config: dict) -> dict:
        """Prepare and validate resource specifications.
        
        This method can be overridden by subclasses to handle
        scheduler-specific resource parameter conversion.
        """
        # Extract common ResourceSpec parameters
        resource_params = {}
        
        # Resource parameters that might be in config
        resource_keys = [
            'cpu_count', 'memory', 'time_limit', 'queue', 'partition',
            'gpu_count', 'gpu_type', 'email', 'email_events', 'priority',
            'exclusive_node', 'node_count', 'cpu_per_node', 'memory_per_cpu',
            'account', 'constraints', 'licenses', 'array_spec', 'workdir'
        ]
        
        for key in resource_keys:
            if key in config:
                resource_params[key] = config[key]
        
        return resource_params

    def convert_unified_to_scheduler_params(self, config: dict) -> dict:
        """Convert unified ResourceSpec parameters to scheduler-specific format.
        
        This is a default implementation that can be overridden by subclasses
        to handle scheduler-specific parameter conversion.
        
        Args:
            config: Job configuration with potential unified parameters
            
        Returns:
            Configuration with scheduler-specific parameters
        """
        # Default implementation just passes through
        # Subclasses should override this for specific conversion logic
        return config
    
    def extract_core_params(self, config: dict) -> tuple[str, str | list[str], dict]:
        """Extract core job parameters from configuration.
        
        Returns:
            Tuple of (job_name, cmd, resource_params)
        """
        job_name = config.get('job_name', 'unnamed_job')
        cmd = config.get('cmd', [])
        
        # Extract resource-related parameters
        resource_params = self.prepare_resource_spec(config)
        
        return job_name, cmd, resource_params

    def modify_node(self, node: Callable[..., Any]) -> Callable[..., Any]:
        """Allow submitters to adapt Hamilton nodes if needed."""
        return node

    @property
    def job_id_list(self):
        """List of tracked job identifiers."""
        return list(self.GLOBAL_JOB_POOL.keys())

    @property
    def jobs(self):
        """Snapshot of the job pool."""
        return self.GLOBAL_JOB_POOL.copy()

    def get_status(self, job_id: int) -> JobStatus | None:
        """Return the :class:`JobStatus` associated with ``job_id``."""
        return self.GLOBAL_JOB_POOL.get(job_id, None)

    def update_status(self, status: dict[int, JobStatus], verbose: bool = False):
        """Replace the internal job pool and optionally print it."""
        self.GLOBAL_JOB_POOL = status
        # self.GLOBAL_JOB_POOL = {k: v for k, v in self.GLOBAL_JOB_POOL.items() if not v.is_finish}
        if verbose:
            self.print_status()

    def monitor_all(
        self, interval: int = 60, verbose: bool = True, callback: Callable | None = None
    ):
        """Poll all jobs until completion."""
        while self.GLOBAL_JOB_POOL:
            self.refresh_status()
            time.sleep(interval)
            if callback:
                callback()

    # backward compat
    def monitor(self, interval: int = 60, verbose: bool = True, callback: Callable | None = None):
        """Backward compatible wrapper for :meth:`monitor_all`."""
        self.monitor_all(interval=interval, verbose=verbose, callback=callback)

    def block_all_until_complete(self, interval: int = 2, verbose: bool = True):
        """Block until every tracked job finishes."""
        while self.GLOBAL_JOB_POOL:
            self.refresh_status()
            time.sleep(interval)

    def block_one_until_complete(
        self, job_id: int, interval: int = 2, verbose: bool = True
    ):
        """Block until ``job_id`` reaches a terminal state."""
        while True:
            self.refresh_status(verbose=False)
            jobstatus = self.get_status(job_id)
            if jobstatus is None or jobstatus.is_finish:
                break
            time.sleep(interval)

    def get_status_by_name(self, name: str):
        """Return the first job whose name has ``name`` as prefix."""
        for status in self.jobs.values():
            if name.startswith(status.name):
                return status
        return None

    def refresh_status(self, verbose: bool = True):
        """Refresh internal status cache from the scheduler."""
        status = self.query()
        self.update_status(status, verbose=verbose)

    def print_status(self):
        """print job status in a nice table

        Args:
            pool (dict[int, JobStatus]): job pool to be printed
        """
        for i, status in enumerate(self.jobs.values(), 1):
            print(f"{status} | {i}/{len(self.GLOBAL_JOB_POOL)} \r", flush=True)
