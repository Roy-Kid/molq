import functools
import inspect
import subprocess
from time import perf_counter
from typing import Callable

from hamilton import driver
from hamilton.ad_hoc_utils import create_temporary_module
from hamilton.execution import executors
from hamilton.execution.executors import DefaultExecutionManager, TaskExecutor
from hamilton.execution.grouping import TaskImplementation
from hamilton.function_modifiers import tag
from hamilton.htypes import Collect, Parallelizable

from typing import Generator


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


def cmdline(func):
    """Decorator to run the result of a function as a command line command."""
    func = tag(cmdline='true')(func)
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if inspect.isgeneratorfunction(func):
            # If the function is a generator, then we need to run it and capture the output
            # in order to return it
            gen = func(*args, **kwargs)
            cmd = next(gen)
            # Run the command and capture the output
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            try:
                gen.send(result)
                raise ValueError("Generator cannot have multiple yields.")
            except StopIteration as e:
                return e.value
        else:
            # Get the command from the function
            cmd = func(*args, **kwargs)

            # Run the command and capture the output
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            # Return the output
            return result.stdout

    if inspect.isgeneratorfunction(func):
        # get the return type and set it as the return type of the wrapper
        wrapper.__annotations__["return"] = inspect.signature(func).return_annotation
    return wrapper


def mapper(seconds: list[int]) -> Parallelizable[int]:
    for sec in seconds:
        yield sec


@cmdline
def worker(mapper: int) -> int:
    print(f"start work {mapper}s")
    start = perf_counter()
    yield f"sleep {str(mapper)}"
    end = perf_counter()
    print(f"end stop {end - start:.2f}s work")
    return mapper


def reducer(worker: Collect[int], reduce_fn: Callable = lambda x: x) -> int:

    return reduce_fn(worker)


logic = create_temporary_module(
    mapper,
    worker,
    reducer,
    module_name="logic",
)

if __name__ == "__main__":

    cmd_executor_manager = CMDLineExecutionManager(
        local_executor=executors.SynchronousLocalTaskExecutor(),
        remote_executor=executors.MultiThreadingExecutor(max_tasks=4),
    )

    dr = (
        driver.Builder()
        .with_modules(logic)
        .enable_dynamic_execution(allow_experimental_mode=True)
        .with_execution_manager(cmd_executor_manager)
        .build()
    )
    start = perf_counter()
    dr.execute(["reducer"], inputs={"seconds": [3, 6]})
    print(f"Time taken: {perf_counter() - start: .2f} seconds")