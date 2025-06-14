from .submitor.base import BaseSubmitor
from .base import YieldDecorator


def get_submitor(cluster_name: str, cluster_type: str):
    """
    Get the submitor for the given cluster name and type.

    Args:
        cluster_name (str): identify name of the cluster
        cluster_type (str): type of the cluster, e.g. slurm, local

    Raises:
        ValueError: if the cluster type is not supported

    Returns:
        _type_: submitor class
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

    # ------------------------------------------------------------------
    # helper APIs
    # ------------------------------------------------------------------

    @classmethod
    def get_n_clusters(cls) -> int:
        """Return number of registered clusters."""
        return len([k for k in cls.CLUSTERS.keys() if not k.startswith("_")])

    @classmethod
    def get_cluster(cls, name: str) -> BaseSubmitor:
        """Return the submitor instance for ``name``."""
        return cls.CLUSTERS[name]

