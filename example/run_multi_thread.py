from time import perf_counter
from typing import Callable, Generator

from hamilton import driver
from hamilton.ad_hoc_utils import create_temporary_module
from hamilton.execution import executors
from hamilton.htypes import Collect, Parallelizable

from h_submitor import submit


def mapper(seconds: list[int]) -> Parallelizable[int]:
    for sec in seconds:
        yield sec


@submit("local_thread", "local")
def worker(mapper: int) -> int:
    print(f"start work {mapper}s")
    start = perf_counter()
    yield {
        "job_name": f"sleep_{mapper}",
        "cmd": [f"sleep {str(mapper)}"],
        "block": True,
    }
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
    dr = (
        driver.Builder()
        .with_modules(logic)
        .enable_dynamic_execution(allow_experimental_mode=True)
        .with_local_executor(executors.SynchronousLocalTaskExecutor())
        .with_remote_executor(
            executors.MultiThreadingExecutor(max_tasks=4)
        )  # default is MultiThreadedExecutor(max_tasks=10)
        .build()
    )
    start = perf_counter()
    dr.execute(["reducer"], inputs={"seconds": [3, 6]})
    print(f"Time taken: {perf_counter() - start: .2f} seconds")