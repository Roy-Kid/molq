from time import perf_counter

import cmd_exec as logic
from hamilton import driver
from hamilton.execution import executors

from h_submitor import CMDLineExecutionManager

if __name__ == "__main__":

    cmd_executor_manager = CMDLineExecutionManager(
        local_executor=executors.SynchronousLocalTaskExecutor(),
        remote_executor=executors.MultiProcessingExecutor(max_tasks=4),
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
