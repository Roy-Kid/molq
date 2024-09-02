from abc import ABC, abstractmethod
from functools import wraps, partial
from inspect import isgeneratorfunction, signature
from typing import Any, Callable

from .monitor import JobStatus, Monitor


class YieldDecorator:

    def __call__(self, func: Callable):
        
        func = self.modify_node(func)
        # if isinstance(func, partial):
        #     _to_be_test_fn = func.func
        # else:
        #     _to_be_test_fn = func

        # if not isgeneratorfunction(_to_be_test_fn):
        #     IS_GENERATOR = True
        # else:
        #     IS_GENERATOR = False

        @wraps(func)
        def wrapper(*args, **kwargs):

            # if function is not generator,
            # either it's cached or it's just impl wrong
            # return the result directly
            if not isgeneratorfunction(func):
                return func(*args, **kwargs)

            generator = func(*args, **kwargs)
            config: dict = next(generator)
            config = self.validate_config(config)

            # do something
            result = self.do(config)

            try:
                generator.send(result)
                # ValueError should not be hit because a StopIteration should be raised, unless
                # there are multiple yields in the generator.
                raise ValueError("Generator cannot have multiple yields.")
            except StopIteration as e:
                result = e.value

            return result

        # get the return type and set it as the return type of the wrapper
        wrapper.__annotations__["return"] = signature(func).return_annotation
        return wrapper
    
    @abstractmethod
    def modify_node(self, func: Callable)->Callable:
        return func

    @abstractmethod
    def do(self, config: dict):
        pass

    @abstractmethod
    def validate_config(self, config: dict)->dict:
        pass

class BaseSubmitor(ABC):

    def __init__(self, cluster_name: str, cluster_config: dict = {}):
        self.cluster_name = cluster_name
        self.cluster_config = cluster_config  # TODO: for remote submitor
        self.monitor = Monitor(self)

    def __repr__(self):
        return f"<{self.__class__.__name__} for {self.cluster_name}>"

    def submit(self, config: dict, remote: bool = False):
        config = self.validate_config(config)
        block = config.get("block", False)
        if remote:
            job_id = self.remote_submit(**config)
        else:
            job_id = self.local_submit(**config)
        return self.after_submit(job_id, block)

    def after_submit(self, job_id: int, block: bool):
        self.monitor.add_job(job_id)
        if block:
            self.monitor.block_until_complete(job_id)
        return job_id
    
    def refresh_status(self):
        self.monitor.add_jobs(self.monitor.job_id_list)
    
    @abstractmethod
    def local_submit(
        self,
        job_name: str,
        cmd: list[str],
        block: bool = False,
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
    def query(self, job_id: int | None) -> JobStatus:
        pass

    @abstractmethod
    def cancel(self, job_id: int):
        pass

    @abstractmethod
    def validate_config(self, config: dict) -> dict:
        return config

    def modify_node(self, node: Callable[..., Any]) -> Callable[..., Any]:
        return node
