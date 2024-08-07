from hamilton import driver
from hamilton.execution import executors
from time import perf_counter

import multi_proc

if __name__ == "__main__":
    dr = (
        driver.Builder()
        .with_modules(multi_proc)  # can not pickle temporary module?
        .enable_dynamic_execution(allow_experimental_mode=True)
        .with_local_executor(executors.SynchronousLocalTaskExecutor())
        .with_remote_executor(
            executors.MultiProcessingExecutor(max_tasks=4)
        )  # default is MultiThreadedExecutor(max_tasks=10)
        .build()
    )
    start = perf_counter()
    dr.execute(["reducer"], inputs={"seconds": [3, 6]})
    print(f"Time taken: {perf_counter() - start: .2f} seconds")

    # ERROR: can not sync job_id from focked process