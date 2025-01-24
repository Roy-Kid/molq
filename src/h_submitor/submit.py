from .submitor.base import BaseSubmitor
from .base import YieldDecorator


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
    """Decorator to submit jobs to different clusters"""

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

    def validate_yield(self, config):
        # submitor handles the config validation
        return config

    def after_yield(self, config):
        return self._current_submitor.submit(config)
