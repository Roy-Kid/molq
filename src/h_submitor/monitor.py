import enum
import time

class JobStatus:

    class Status(enum.Enum):
        PENDING = 1
        RUNNING = 2
        COMPLETED = 3
        FAILED = 4
        FINISHED = 5

    def __init__(self, job_id: int, status: Status, name: str = "", **others: str):
        self.name: str = name
        self.job_id: int = job_id
        self.status: str = status

        self.others: dict[str] = others

    def __repr__(self):
        return f"<Job {self.name}({self.job_id}): {self.status}>"

    @property
    def is_finish(self) -> bool:
        return self.status in [
            JobStatus.Status.COMPLETED,
            JobStatus.Status.FAILED,
            JobStatus.Status.FINISHED,
        ]

class Monitor:

    job_pool: dict[int, JobStatus] = dict()

    def __init__(self, submitor):
        self.submitor = submitor

    @property
    def job_id_list(self):
        return list(self.job_pool.keys())

    @property
    def jobs(self):
        return self.job_pool.copy()

    def add_job(self, job_id: int):
        self.job_pool[job_id] = self.submitor.query(job_id)

    def add_jobs(self, job_ids: list[int]):
        for id_ in job_ids:
            self.job_pool[id_] = self.submitor.query(id_)

    def monitor_all(self, interval: int = 60):
        while self.job_pool:
            for job_id in self.job_id_list:
                job_status = self.submitor.query(job_id)
                if job_status.is_finish:
                    self.job_pool.pop(job_id)
                else:
                    self.job_pool[job_id] = job_status
                time.sleep(interval)

            self.print_status()

    def block_until_complete(self, job_id: int, interval: int = 2):
        while True:
            job_status = self.submitor.query(job_id)
            print(job_status)
            if job_status.is_finish:
                if job_id in self.job_pool:
                    self.job_pool.pop(job_id)
                break
            time.sleep(interval)

    def print_status(self):
        """print job status in a nice table

        Args:
            pool (dict[int, JobStatus]): job pool to be printed
        """
        for i, status in enumerate(self.jobs.values(), 1):
            print(f"{status} | {i}/{len(self.job_pool)}", flush=True)