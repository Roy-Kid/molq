from time import perf_counter
from typing import Callable, Generator

from hamilton import driver
from hamilton.ad_hoc_utils import create_temporary_module
from hamilton.execution import executors
from hamilton.htypes import Collect, Parallelizable
from hamilton.lifecycle.default import CacheAdapter

from h_submitor import submit, cmdline


@cmdline
def worker(seconds: int) -> int:
    print(f"start work {seconds}s")
    start = perf_counter()
    yield {
        "job_name": f"sleep_{seconds}",
        "cmd": [f"sleep {str(seconds)}"],
        "block": True,
    }
    end = perf_counter()
    print(f"end stop {end - start:.2f}s work")
    return seconds

logic = create_temporary_module(
    worker,
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
        .with_adapters(CacheAdapter(cache_path="cache"))
        .build()
    )
    start = perf_counter()
    dr.execute(["worker"], inputs={"seconds": 3})
    print(f"Time taken: {perf_counter() - start: .2f} seconds")