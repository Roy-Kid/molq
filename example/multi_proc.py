from hamilton import driver
from hamilton.ad_hoc_utils import create_temporary_module
from hamilton.execution import executors

from typing import Callable

from hamilton.htypes import Collect, Parallelizable

from h_submitor import submit

from time import perf_counter


import multiprocessing

def mapper(seconds: list[int]) -> Parallelizable[int]:
    for sec in seconds:
        yield sec


@submit("local_thread", "local")
def worker(mapper: int) -> int:
    print(f"start work {mapper}s")
    start = perf_counter()
    print(multiprocessing.current_process())
    yield {
        "job_name": f"sleep_{mapper}",
        "cmd": [f"sleep {str(mapper)}"],
        "monitor": True,
        "block": False,
    }
    end = perf_counter()
    print(f"end stop {end - start:.2f}s work")
    return mapper


def reducer(worker: Collect[int], reduce_fn: Callable = lambda x: x) -> int:

    submit('local_thread').monitor.monitor_all(1)

    print(multiprocessing.current_process())

    return reduce_fn(worker)
