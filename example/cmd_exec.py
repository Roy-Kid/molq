import multiprocessing
from time import perf_counter
from typing import Callable
from hamilton.htypes import Collect, Parallelizable

from h_submitor import cmdline


def mapper(seconds: list[int]) -> Parallelizable[int]:
    for sec in seconds:
        yield sec


@cmdline
def worker(mapper: int) -> int:
    print(f"start work {mapper}s")
    start = perf_counter()
    cur_proc = multiprocessing.current_process()
    print(f"worker on {cur_proc.name}")
    stdout = yield {
        "cmd": ["sleep", f"{mapper}"],
        "block": True,
    }
    print(stdout)
    end = perf_counter()
    print(f"end stop {end - start:.2f}s work")
    return mapper


def reducer(worker: Collect[int], reduce_fn: Callable = lambda x: x) -> int:

    return reduce_fn(worker)
