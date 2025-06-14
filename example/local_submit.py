"""Submit a job to the local machine."""

from molq import submit
from typing import Generator, Any

local = submit("local", "local")

@local
def sleep_job() -> Generator[dict, int, int]:
    job_id = yield {
        "job_name": "sleep_1",
        "cmd": ["sleep", "1"],
        "block": True,
    }
    return job_id

if __name__ == "__main__":
    print("Job id", sleep_job())
