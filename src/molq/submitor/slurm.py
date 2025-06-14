# pragma: no cover - heavy interaction with SLURM
import subprocess
from pathlib import Path
from typing import Dict, Any, Union, List, Optional

from .base import BaseSubmitor, JobStatus


class SlurmSubmitor(BaseSubmitor):
    """Submit jobs to a SLURM workload manager."""

    def local_submit(
        self,
        job_name: str,
        cmd: str | list[str],
        cwd: str | Path | None = None,
        block: bool = False,
        # Traditional SLURM parameters (for backward compatibility)
        n_cores: int | None = None,  # --ntasks
        memory_max: int | None = None,  # --mem
        run_time_max: str | int | None = None,  # --time
        partition: str | None = None,  # --partition
        account: str | None = None,  # --account
        # Unified resource specification parameters
        cpu_count: int | None = None,
        memory: str | None = None,
        time_limit: str | None = None,
        queue: str | None = None,
        gpu_count: int | None = None,
        gpu_type: str | None = None,
        email: str | None = None,
        email_events: List[str] | None = None,
        priority: str | None = None,
        exclusive_node: bool | None = None,
        script_name: str | Path = "run_slurm",
        work_dir: Path | None = None,
        test_only: bool = False,
        **slurm_kwargs,
    ) -> int:
        """Create a SLURM script and submit it with ``sbatch``."""
        # Convert unified parameters to traditional SLURM parameters
        submit_config = self._prepare_slurm_config(
            job_name=job_name,
            n_cores=n_cores,
            memory_max=memory_max,
            run_time_max=run_time_max,
            partition=partition,
            account=account,
            cpu_count=cpu_count,
            memory=memory,
            time_limit=time_limit,
            queue=queue,
            gpu_count=gpu_count,
            gpu_type=gpu_type,
            email=email,
            email_events=email_events,
            priority=priority,
            exclusive_node=exclusive_node,
            **slurm_kwargs
        )
        
        # Set working directory
        if work_dir is None:
            work_dir = Path(cwd) if cwd else Path.cwd()
        
        # Ensure cmd is a list
        if isinstance(cmd, str):
            cmd = [cmd]
        
        script_path = self._gen_script(Path(work_dir) / script_name, cmd, **submit_config)

        submit_cmd = ["sbatch", str(script_path.absolute()), "--parsable"]

        if test_only:
            submit_cmd.append("--test-only")

        submit_cmd.append(str(script_name))

        try:
            proc = subprocess.run(submit_cmd, capture_output=True)
            # script_path.unlink()
        except subprocess.CalledProcessError as e:
            raise e

        if test_only:
            # example output:
            # sbatch: Job 3676091 to start at 2024-04-26T20:02:12 using 256 processors on nodes nid001000 in partition main
            job_id = int(proc.stderr.split()[2])
        else:
            job_id = int(proc.stdout)

        return job_id

    def remote_submit(self):
        """Submit a job to a remote SLURM cluster (unimplemented)."""
        pass  # pragma: no cover

    # public helper for tests
    def gen_script(self, script_path: str | Path, cmd: list[str], **kwargs) -> Path:
        """Public helper used in tests to generate a SLURM script."""
        return self._gen_script(Path(script_path), cmd, **kwargs)

    def _gen_script(self, script_path: Path, cmd: list[str], **kwargs) -> Path:
        """Write a SLURM submission script and return its path."""
        assert script_path.parent.exists(), f"{script_path.parent} does not exist"
        with open(script_path, "w") as f:
            f.write("#!/bin/bash\n")
            for key, value in kwargs.items():
                f.write(f"#SBATCH {key}={value}\n")
            f.write("\n")
            f.write("\n".join(cmd))
        return script_path

    def query(self, job_id: int | None = None) -> dict[int, JobStatus]:
        """Query the scheduler for job status using ``squeue``."""
        if job_id is None:
            cmd = ["squeue"]
        else:
            cmd = ["squeue", "-j", str(job_id)]
        
        proc = subprocess.run(cmd, capture_output=True)
        out = proc.stdout.decode()
        
        try:
            lines = out.strip().split("\n")
            if len(lines) < 2:
                return {}
            
            header = lines[0]
            result = {}
            
            for job_line in lines[1:]:
                if not job_line.strip():
                    continue
                    
                status = {k: v for k, v in zip(header.split(), job_line.split())}
                if "JOBID" not in status:
                    continue
                    
                if "ST" not in status:
                    # Try different column name
                    status_key = "STATE" if "STATE" in status else "ST"
                else:
                    status_key = "ST"
                
                if status_key not in status:
                    continue
                
                if status[status_key] == "R":
                    enum_status = "RUNNING"
                elif status[status_key] == "PD":
                    enum_status = "PENDING"
                elif status[status_key] == "CD":
                    enum_status = "COMPLETED"
                else:
                    enum_status = "FAILED"
                
                job_status = JobStatus(
                    job_id=int(status["JOBID"]),
                    status=JobStatus.Status[enum_status],
                    name=status.get("NAME", ""),
                    partition=status.get("PARTITION", ""),
                    user=status.get("USER", ""),
                    time=status.get("TIME", ""),
                    nodes=status.get("NODES", "0"),
                    nodelist=status.get("NODELIST(REASON)", ""),
                )
                result[job_status.job_id] = job_status
            
            return result
            
        except Exception as e:
            if job_id:
                raise ValueError(f"can not find {job_id} in {out}") from e
            else:
                return {}

    def validate_config(self, config: dict) -> dict:
        """Validate the configuration before submission."""
        return super().validate_config(config)

    def cancel(self, job_id: int) -> None:
        """Cancel a submitted SLURM job."""
        cmd = ["scancel", str(job_id)]
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to cancel job {job_id}: {proc.stderr.decode()}")

    def _prepare_slurm_config(
        self,
        job_name: str,
        n_cores: int | None = None,
        memory_max: int | None = None,
        run_time_max: str | int | None = None,
        partition: str | None = None,
        account: str | None = None,
        cpu_count: int | None = None,
        memory: str | None = None,
        time_limit: str | None = None,
        queue: str | None = None,
        gpu_count: int | None = None,
        gpu_type: str | None = None,
        email: str | None = None,
        email_events: List[str] | None = None,
        priority: str | None = None,
        exclusive_node: bool | None = None,
        **slurm_kwargs
    ) -> Dict[str, Any]:
        """Convert unified resource parameters to SLURM configuration."""
        submit_config = slurm_kwargs.copy()
        submit_config["--job-name"] = job_name
        
        # Use unified parameters if available, otherwise fall back to traditional ones
        final_cpu_count = cpu_count or n_cores
        final_memory = memory or memory_max
        final_time = time_limit or run_time_max
        final_partition = queue or partition
        
        # Set CPU count
        if final_cpu_count:
            submit_config["--ntasks"] = final_cpu_count
        
        # Handle memory conversion
        if final_memory:
            if isinstance(final_memory, str):
                # Convert human-readable format to SLURM format
                submit_config["--mem"] = self._convert_memory_format(final_memory)
            else:
                submit_config["--mem"] = final_memory
        
        # Handle time conversion
        if final_time:
            if isinstance(final_time, str):
                submit_config["--time"] = self._convert_time_format(final_time)
            else:
                submit_config["--time"] = final_time
        
        # Set other parameters
        options = {
            "--partition": final_partition,
            "--account": account,
        }
        
        # GPU resources
        if gpu_count:
            if gpu_type:
                submit_config["--gres"] = f"gpu:{gpu_type}:{gpu_count}"
            else:
                submit_config["--gres"] = f"gpu:{gpu_count}"
        
        # Email notifications
        if email:
            submit_config["--mail-user"] = email
        if email_events:
            # Convert email events to SLURM format
            mail_type = self._convert_email_events(email_events)
            if mail_type:
                submit_config["--mail-type"] = mail_type
        
        # Priority
        if priority:
            submit_config["--priority"] = self._convert_priority(priority)
        
        # Exclusive node
        if exclusive_node:
            submit_config["--exclusive"] = ""
        
        # Add non-None options
        submit_config.update({k: v for k, v in options.items() if v is not None})
        
        return submit_config
    
    def _convert_memory_format(self, memory: str) -> str:
        """Convert human-readable memory format to SLURM format."""
        try:
            from molq.resources import MemoryParser
            return MemoryParser.to_slurm_format(memory)
        except ImportError:
            # Fallback: assume it's already in correct format
            return memory
    
    def _convert_time_format(self, time_str: str) -> str:
        """Convert human-readable time format to SLURM format."""
        try:
            from molq.resources import TimeParser
            return TimeParser.to_slurm_format(time_str)
        except ImportError:
            # Fallback: assume it's already in correct format
            return time_str
    
    def _convert_email_events(self, events: List[str]) -> str:
        """Convert email events to SLURM mail-type format."""
        event_map = {
            'start': 'BEGIN',
            'end': 'END',
            'fail': 'FAIL',
            'all': 'ALL'
        }
        slurm_events = [event_map.get(event.lower(), event.upper()) for event in events]
        return ','.join(slurm_events)
    
    def _convert_priority(self, priority: str) -> str:
        """Convert priority level to SLURM numeric priority."""
        priority_map = {
            'low': '100',
            'normal': '500',
            'high': '1000'
        }
        return priority_map.get(priority.lower(), priority)

