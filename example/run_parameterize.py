from time import perf_counter
from typing import Callable

from hamilton import driver
from hamilton.ad_hoc_utils import create_temporary_module
from hamilton.execution import executors
from hamilton.function_modifiers import parameterize, value

from h_submitor import submit


@submit("local_thread", "local")
@parameterize(
    **{f"work_{sec}s": {"second": value(sec)} for sec in [3, 6]}
)
def worker(second: int) -> int:
    print(f"start work {second}s")
    start = perf_counter()
    yield {
        "job_name": f"sleep_{second}",
        "cmd": [f"sleep {str(second)}"],
        "monitor": False,
        "block": True,
    }
    end = perf_counter()
    print(f"end stop {end - start:.2f}s work")
    return second


logic = create_temporary_module(
    worker,
    module_name="logic",
)

if __name__ == "__main__":
    dr = (
        driver.Builder()
        .with_modules(logic)
        .enable_dynamic_execution(allow_experimental_mode=True)
        .with_local_executor(executors.SynchronousLocalTaskExecutor())
        # .with_remote_executor(
        #     executors.MultiThreadingExecutor(max_tasks=4)
        # )  parallel execution is not supported parameterize function
        .build()
    )
    start = perf_counter()
    dr.execute([f"work_{sec}s" for sec in [3, 6]])
    print(f"Time taken: {perf_counter() - start: .2f} seconds")