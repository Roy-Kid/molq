import subprocess
from typing import Callable
from .base import YieldDecorator

from hamilton.execution.executors import DefaultExecutionManager, TaskExecutor
from hamilton.execution.grouping import TaskImplementation
from hamilton.function_modifiers import tag


class CMDLineExecutionManager(DefaultExecutionManager):
    def get_executor_for_task(self, task: TaskImplementation) -> TaskExecutor:
        """Simple implementation that returns the local executor for single task executions,
        :param task: Task to get executor for
        :return: A local task if this is a "single-node" task, a remote task otherwise
        """
        is_single_node_task = len(task.nodes) == 1
        if not is_single_node_task:
            raise ValueError("Only single node tasks supported")
        (node,) = task.nodes
        if "cmdline" in node.tags:  # hard coded for now
            return self.remote_executor
        return self.local_executor


class cmdline(YieldDecorator):
    """Decorator to run the result of a function as a command line command.
    """

    def modify_func(self, func: Callable)->Callable:
        func = tag(cmdline='true')(func)
        return func

    def validate_config(self, config: dict)->dict:

        default_config = {
            'block': True,
            'kwargs': {
                'capture_output': True,
                'shell': False,
            }
        }

        config |= default_config
        
        cmd = config.get('cmd')
        assert isinstance(cmd, (list, str)), ValueError(f"cmd must be a list of string or a string, got {type(cmd)}")

        return config

    def do(self, config: dict) -> subprocess.CompletedProcess:

        cmd = config.get('cmd')
        kwargs = config.get('kwargs')

        result = subprocess.run(cmd, **kwargs)

        return result
        
