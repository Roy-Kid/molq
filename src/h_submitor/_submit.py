from pathlib import Path
import inspect
import functools
import subprocess
from time import sleep

def setup_adapter(cluster_name: str, cluster_type: str):
    if cluster_type == "slurm":
        return SlurmAdapter(cluster_name)
    else:
        raise ValueError(f"Cluster type {cluster_type} not supported.")
    

# class Monitor:
#     """
#     Global monitor for all jobs submitted. It runs in a separate process and queries the status of all jobs in different clusters.
#     """
#     monitor_process: subprocess.Popen | None = None
#     monitor_jobs: list[int] = []

#     def __init__(self, query_mehtod: callable, interval: int = 60):
#         self.query_method = query_mehtod
#         self.interval = interval

#     def start(self):
#         if Monitor.monitor_process is None:
#             Monitor.monitor_process = multiprocessing.Process(target=self._monitor)
#             Monitor.monitor_process.start()

#     def watch(self, job_id: int):
#         Monitor.monitor_jobs.append(job_id)
#         # for example, if we want to submit 20 jobs with a loop, we dont know which submit is last one:
#         # ```
#         # for inputs in inputs_list:
#         #     dr.execute(inputs)
#         # ```
#         # so we need to restart multiprocessing for each execution
#         #   to update monitor_jobs list

#         # or we set a global flag e.g.:
#         # ```
#         # for inputs in inputs_list:
#         #     dr.execute(inputs)
#         # import Monitor
#         # proc: Popen = Monitor.start()
#         # ````
#         # then we maybe can finish our workflow as non-blocking mode,
#         # when we want to know the status of jobs, 
#         # we can manually get process from background
#         self.start()

#     def _monitor(self):


class SubmitAdapter:

    def __init__(self, cluster_name: str, cluster_type: str):
        self.cluster_name = cluster_name
        self.cluster_type = cluster_type

        # self.queue: list[int] = []

    def __repr__(self):
        return f"<SubmitAdapter: {self.cluster_name}({self.cluster_type})>"
    
    def submit(
        self,
        cmd: list[str],
        job_name: str,
        n_cores: int,
        memory_max: int | None = None,
        run_time_max: str | int | None = None,
        work_dir: Path | str | None = None,
        script_name: str|Path = "run_slurm.sh",
        **args,
    ):
        raise NotImplementedError
    
    def remote_submit(self):
        # TODO: use ssh and scp to submit job to remote cluster
        # third-party library: paramiko
        # license: LGPL
        # https://www.paramiko.org/
        raise NotImplementedError

    def _write_submit_script(self, script_name: str, **args):
        raise NotImplementedError
    
    def query(self, job_id: int|None):
        raise NotImplementedError
    
    def watch(self, job_id: int):
        pass

    def monitor(self, job_id:int):
        pass



class SlurmAdapter(SubmitAdapter):

    def __init__(self, cluster_name: str):
        super().__init__(cluster_name, "slurm")

    def submit(
        self,
        cmd: list[str],
        job_name: str,
        n_cores: int,
        memory_max: int | None = None,
        run_time_max: str | int | None = None,
        work_dir: Path | str | None = None,
        account: str | None = None,
        script_name: str|Path = "run_slurm.sh",
        is_monitor: bool = False,
        test_only: bool = False,
        **slurm_kwargs,
    ):

        slurm_kwargs["--job-name"] = job_name
        slurm_kwargs["--ntasks"] = n_cores
        if memory_max:
            slurm_kwargs["--mem"] = memory_max
        if run_time_max:
            slurm_kwargs["--time"] = run_time_max
        if work_dir:
            slurm_kwargs["--chdir"] = work_dir
        if account:
            slurm_kwargs["--account"] = account
        
        submit_cmd = ["sbatch", "--parsable"]
        
        if test_only:
            submit_cmd.append("--test-only")

        submit_cmd.append(script_name)

        self._write_submit_script(Path(script_name), cmd, **slurm_kwargs)

        try:
            proc = subprocess.run(submit_cmd, capture_output=True)
        except subprocess.CalledProcessError as e:
            raise e

        if test_only:
            # sbatch: Job 3676091 to start at 2024-04-26T20:02:12 using 256 processors on nodes nid001000 in partition main
            print(proc.stderr)
            job_id = int(proc.stderr.split()[2])
        else:
            job_id = int(proc.stdout)

        if is_monitor:
            self.watch(job_id)

        return job_id
    
    def watch(self, job_id:int):
        info = self.query(job_id)
        while info:
            info = self.query(job_id)
            print(f"Job {job_id}")
            sleep(10)

    def _write_submit_script(self, script_path: Path, cmd: list[str], **args):
        # assert script_path.exists(), f"Script path {script_path} does not exist."
        with open(script_path, "w") as f:
            f.write("#!/bin/bash\n")
            for key, value in args.items():
                f.write(f"#SBATCH {key}={value}\n")
            f.write("\n".join(cmd))
            f.write("\n")

    def query(self, job_id: int):
        proc = subprocess.run(f"squeue -j {job_id}", shell=True, check=True, capture_output=True)
        info = proc.stdout.decode('utf-8').split("\n")
        header = info[0]
        if len(info) > 2:
            info_dict = {k: v for k, v in zip(header.split(), info[1].split())}
        else:
            info_dict = {}
        return info_dict

    def remote_submit(self):
        pass


class BaseSubmitor:

    cluster: dict[str, SubmitAdapter] = {}

    def __new__(cls, cluster_name: str, cluster_type: str=None):

        if cluster_name not in BaseSubmitor.cluster:
            cls.cluster[cluster_name] = setup_adapter(cluster_name, cluster_type)

        return super().__new__(cls)

    def __init__(self, cluster_name: str, *args, **kwargs):
        self._adapter = BaseSubmitor.cluster[cluster_name]

    def submit(
        self,
        cmd: list[str],
        job_name: str,
        n_cores: int,
        memory_max: int | None = None,
        run_time_max: str | int | None = None,
        script_name: str|Path|None = "run_slurm.sh",
        uploads: list[Path] | None = None,
        downloads: list[Path] | None = None,
        is_monitor: bool = False,
        **kwargs,
    ):
        job_id = self._adapter.submit(
            cmd=cmd,
            job_name=job_name,
            n_cores=n_cores,
            memory_max=memory_max,
            run_time_max=run_time_max,
            script_name=script_name,
            is_monitor=is_monitor,
            **kwargs
        )

        return job_id
    
    def query(self, job_id: int):
        return self._adapter.query(job_id)
    
    @property
    def queue(self):
        return self._adapter.queue


def submit(cluster_name: str, cluster_type: str):
    """submit a task to a cluster using the specified cluster type.

    Args:
        cluster_name (str): a name representing a cluster
        cluster_type (str): a type of cluster

    """
    submitor = BaseSubmitor(cluster_name, cluster_type)

    def decorator(func):
        if not inspect.isgeneratorfunction(func):
            raise ValueError("Function must be a generator.")

        @functools.wraps(func)
        def wrapper(*args, **kwargs):

            # submit docrated function must be a generator
            generator = func(*args, **kwargs)
            arguments: dict = next(generator)
            is_remote = arguments.pop("is_remote", False)
            if is_remote:
                raise NotImplementedError("Remote submission is not implemented.")
            else:
                print(f'### Submitting job to {cluster_name} cluster ###')
                job_id = submitor.submit(**arguments)
            
            try:
                generator.send(job_id)
                # ValueError should not be hit because a StopIteration should be raised, unless
                # there are multiple yields in the generator.
                raise ValueError("Generator cannot have multiple yields.")
            except StopIteration as e:
                result = e.value

            return result

        # get the return type and set it as the return type of the wrapper
        wrapper.__annotations__["return"] = inspect.signature(func).return_annotation
        return wrapper

    return decorator