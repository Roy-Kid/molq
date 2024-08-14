import multiprocessing
from time import perf_counter
from typing import Callable, Generator, Any

from hamilton.htypes import Collect, Parallelizable

from h_submitor import submit


def mapper(seconds: list[int]) -> Parallelizable[int]:
    for sec in seconds:
        yield sec


@submit("local_thread", "local")
def worker(mapper: int) -> Generator[dict, Any, int]:
    print(f"start work {mapper}s")
    start = perf_counter()
    print(multiprocessing.current_process())
    yield {
        "job_name": f"sleep_{mapper}",
        "cmd": [f"sleep {str(mapper)}"],
        "monitor": True,
        "block": True,
    }
    end = perf_counter()
    print(f"end stop {end - start:.2f}s work")
    return mapper


def reducer(worker: Collect[int], reduce_fn: Callable = lambda x: x) -> int:

    submit('local_thread').monitor.monitor_all(1)

    print(multiprocessing.current_process())

    return reduce_fn(worker)
