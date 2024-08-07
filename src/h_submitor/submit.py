from functools import wraps
from inspect import isgeneratorfunction, signature
from typing import Callable

from h_submitor.submitor import BaseSubmitor, get_submitor, Monitor


class submit:

    CONFIG = dict()
    CLUSTERS: dict[str, BaseSubmitor] = dict()

    def __new__(
        cls,
        cluster_name: str,
        cluster_type: str | None = None,
    ):
        if cluster_name not in cls.CLUSTERS:
            cls.CLUSTERS[cluster_name] = get_submitor(cluster_name, cluster_type)
        return super().__new__(cls)

    def __init__(
        self,
        cluster_name: str,
        cluster_type: str | None = None,
    ):
        self._adapter = submit.CLUSTERS[cluster_name]

    @classmethod
    def get_n_clusters(self):
        return len(submit.CLUSTERS)

    def __call__(self, func: Callable):

        if not isgeneratorfunction(func):
            raise TypeError(
                f"Function {func.__name__} to be submitted to {self._adapter.type} must be a  generator function"
            )

        @wraps(func)
        def wrapper(*args, **kwargs):

            generator = func(*args, **kwargs)
            submit_config: dict = next(generator)
            job_id = self._adapter.submit(**submit_config)

            try:
                generator.send(job_id)
                # ValueError should not be hit because a StopIteration should be raised, unless
                # there are multiple yields in the generator.
                raise ValueError("Generator cannot have multiple yields.")
            except StopIteration as e:
                result = e.value

            return result

        # get the return type and set it as the return type of the wrapper
        wrapper.__annotations__["return"] = signature(func).return_annotation
        return wrapper

    @property
    def monitor(self) -> Monitor:
        return self._adapter.monitor