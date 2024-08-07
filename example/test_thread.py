from typing import Callable

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
    import time

    print(f"start sleep {mapper}")
    yield {
        'job_name': f"sleep_{mapper}",
        'cmd': [f'sleep {str(mapper)}'],
        'monitor' : 1
    }
    print(f"end sleep {mapper}")
    return mapper


def reducer(worker: Collect[int], reduce_fn: Callable = sum) -> int:
    return reduce_fn(worker)


module = create_temporary_module(mapper, worker, reducer, module_name="temp_module")

if __name__ == "__main__":
    dr = (
        driver.Builder()
        .with_modules(module)
        .enable_dynamic_execution(allow_experimental_mode=True)
        .with_local_executor(executors.SynchronousLocalTaskExecutor())
        .with_remote_executor(
            executors.MultiThreadingExecutor(max_tasks=4)
        )  # default is MultiThreadedExecutor(max_tasks=10)
        .build()
    )
    dr.execute(["reducer"], inputs={"seconds": [5, 10]})
