# Job Management

Molq provides a comprehensive job management system that tracks, monitors, and manages computational jobs across different execution environments.

## Overview

The job management system consists of:

- **SQLite Database**: Persistent storage for job metadata and status (`~/.molq/jobs.db`)
- **Automatic Status Updates**: Real-time job status synchronization
- **CLI Interface**: Command-line tools for interactive job management
- **Multi-Backend Support**: Unified interface for local and SLURM jobs

## Job Database

All jobs are stored in a local SQLite database located at `~/.molq/jobs.db`. The database maintains:

- Job metadata (ID, name, command, working directory)
- Execution status and timestamps
- Resource specifications
- Additional job-specific information

### Database Schema

```sql
CREATE TABLE jobs (
    section TEXT,           -- Scheduler type (local, slurm)
    job_id INTEGER,         -- Job identifier
    job_name TEXT,          -- Human-readable job name
    status TEXT,            -- Current status (PENDING, RUNNING, COMPLETED, FAILED)
    command TEXT,           -- Executed command
    work_dir TEXT,          -- Working directory
    submit_time REAL,       -- Submission timestamp
    start_time REAL,        -- Start timestamp (optional)
    end_time REAL,          -- Completion timestamp (optional)
    extra_info TEXT,        -- Additional JSON metadata
    PRIMARY KEY (section, job_id)
);
```

## Job Status Tracking

Molq automatically tracks job status throughout the execution lifecycle:

- **PENDING**: Job is queued but not yet running
- **RUNNING**: Job is currently executing
- **COMPLETED**: Job finished successfully
- **FAILED**: Job terminated with an error
- **CANCELLED**: Job was manually cancelled

Status updates occur automatically when:
- Listing jobs via CLI (`molq list`)
- Checking individual job status (`molq status <job_id>`)
- Programmatically querying job status

### Status Refresh Mechanism

**Local Jobs**: Uses `os.kill(pid, 0)` to check if processes are still running
**SLURM Jobs**: Uses `squeue` for active jobs and `sacct` for completed jobs

## Command Line Interface

### Job Submission

```bash
# Submit a simple command
molq submit --scheduler local --cmd "echo hello" --job-name greeting

# Submit with resource specifications
molq submit --scheduler slurm \
    --cmd "python train_model.py" \
    --job-name ml-training \
    --cpu-count 8 \
    --memory 32GB \
    --time-limit 2:00:00

# Submit with working directory
molq submit --scheduler local \
    --cmd "make build" \
    --job-name build-project \
    --cwd /path/to/project
```

### Job Monitoring

```bash
# List all active jobs
molq list

# List all jobs including completed ones
molq list --all-history

# List jobs for a specific scheduler
molq list --scheduler local
molq list --scheduler slurm

# Check status of a specific job
molq status 12345

# Cancel a running job
molq cancel 12345
```

### Database Management

```bash
# Reset job database (for testing)
molq config reset-db

# Show configuration
molq config show
```

## Programmatic Usage

### Job Submission with Decorators

```python
from molq import submit
from molq.resources import BaseResourceSpec

# Create a local submitter
local = submit('my_project', 'local')

@local
def run_analysis():
    """Submit a data analysis job."""
    spec = BaseResourceSpec(
        cmd=['python', 'analyze_data.py', '--input', 'data.csv'],
        job_name='data-analysis',
        cpu_count=4,
        memory='8GB'
    )
    job_id = yield spec.model_dump()
    return job_id

# Submit the job
job_id = run_analysis()
```

### Direct Submitter Usage

```python
from molq.submitor.local import LocalSubmitor

submitter = LocalSubmitor()

# Submit a job
job_id = submitter.local_submit(
    job_name='test-job',
    cmd=['echo', 'Hello World'],
    cpu_count=2,
    memory='4GB'
)

# Check job status
status = submitter.refresh_job_status(job_id)
print(f"Job {job_id} status: {status.status}")

# List all jobs
jobs = submitter.list_jobs('local')
submitter.print_jobs(jobs)
```

## Configuration

### Directory Structure

The system stores data in `~/.molq/`:

```
~/.molq/
├── jobs.db                # SQLite database for job tracking
├── local_jobs.json        # Legacy local job tracking (compatibility)
└── config.json           # Configuration settings (future use)
```

### Environment Variables

- `MOLQ_HOME`: Override default configuration directory
- `MOLQ_DB_PATH`: Override database file location

## Testing Integration

For testing, Molq provides utilities to isolate job data:

```python
import pytest
from molq.submitor.base import BaseSubmitor

def test_job_management(tmp_path, monkeypatch):
    # Use temporary directory for job database
    monkeypatch.setenv("HOME", str(tmp_path))
    
    submitter = BaseSubmitor()
    
    # Test job operations
    submitter.register_job(
        section='local',
        job_id=123,
        job_name='test-job',
        status=JobStatus.Status.RUNNING
    )
    
    jobs = submitter.list_jobs('local')
    assert len(jobs) == 1
    
    # Database is automatically cleaned up with tmp_path
```

## Troubleshooting

### Common Issues

**Database locked**: Ensure no other Molq processes are running
**Permission denied**: Check file permissions in `~/.molq/` directory
**Status not updating**: Verify scheduler access (SLURM commands available)

### Debug Mode

Enable debug logging for detailed information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Your Molq code here
```

### Reset Database

If the database becomes corrupted:

```bash
molq config reset-db
```

Or manually:

```bash
rm ~/.molq/jobs.db
```
