from typing import Callable, Any

from h_submitor.submitor import BaseSubmitor, Monitor, get_submitor

from .base import YieldDecorator


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
