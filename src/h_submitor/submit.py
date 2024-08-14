from typing import Callable, Any

from .base import BaseSubmitor, YieldDecorator
from .monitor import Monitor


def get_submitor(cluster_name: str, cluster_type: str):
    """factory function to get submitor instance

    :param cluster_name: a unique custom name representing the cluster
    :type cluster_name: str
    :param cluster_type: type of the cluster, e.g. "slurm", "local"
    :type cluster_type: str
    :raises ValueError: if cluster type not supported
    :return: submitor instance
    :rtype: BaseSubmitor
    """
    if cluster_type == "slurm":
        from .submitor.slurm import SlurmSubmitor

        return SlurmSubmitor(cluster_name)
    elif cluster_type == "local":
        from .submitor.local import LocalSubmitor

        return LocalSubmitor(cluster_name)
    else:
        raise ValueError(f"Cluster type {cluster_type} not supported.")


class submit(YieldDecorator):

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
        self._current_submitor = submit.CLUSTERS[cluster_name]

    def modify_node(self, node: Callable[..., Any]) -> Callable[..., Any]:
        return self._current_submitor.modify_node(node)

    def do(self, config: dict) -> Any:
        return self._current_submitor.submit(config)

    def validate_config(self, config: dict) -> dict:
        return self._current_submitor.validate_config(config)

    @property
    def monitor(self) -> Monitor:
        return self._current_submitor.monitor
