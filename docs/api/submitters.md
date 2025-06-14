# Submitters API Reference

This section provides comprehensive API documentation for Molq's job submitters, including the base classes and specific implementations for different execution backends.

## Base Classes

### BaseSubmitor

The abstract base class that defines the interface for all job submitters.

```python
from molq.submitor import BaseSubmitor
```

#### Methods

##### `__init__(self, config: dict)`

Initialize the submitter with configuration.

**Parameters:**
- `config` (dict): Configuration dictionary specific to the submitter type

##### `submit_job(self, job_spec: dict) -> int`

Submit a job and return its ID.

**Parameters:**
- `job_spec` (dict): Job specification dictionary

**Returns:**
- `int`: Job ID assigned by the submitter

**Raises:**
- `SubmissionError`: If job submission fails

##### `get_job_status(self, job_id: int) -> str`

Get the current status of a job.

**Parameters:**
- `job_id` (int): Job ID to check

**Returns:**
- `str`: Job status (varies by submitter type)

**Raises:**
- `JobNotFoundError`: If job ID is not found

##### `get_job_info(self, job_id: int) -> dict`

Get detailed information about a job.

**Parameters:**
- `job_id` (int): Job ID to query

**Returns:**
- `dict`: Dictionary containing job details

**Raises:**
- `JobNotFoundError`: If job ID is not found

##### `cancel_job(self, job_id: int) -> bool`

Cancel a running or pending job.

**Parameters:**
- `job_id` (int): Job ID to cancel

**Returns:**
- `bool`: True if cancellation was successful

**Raises:**
- `JobNotFoundError`: If job ID is not found

##### `get_queue_info(self) -> list`

Get information about jobs in the queue.

**Returns:**
- `list[dict]`: List of job information dictionaries

## Local Submitter

### LocalSubmitor

Submitter for executing jobs locally on the current machine.

```python
from molq.submitor import LocalSubmitor

# Initialize
submitter = LocalSubmitor({
    'max_concurrent_jobs': 4,
    'working_directory': '/tmp/jobs',
    'environment': {'PATH': '/usr/bin:/bin'}
})
```

#### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_concurrent_jobs` | int | `None` | Maximum simultaneous jobs (None = unlimited) |
| `job_timeout` | int | `None` | Job timeout in seconds |
| `working_directory` | str | current dir | Working directory for jobs |
| `shell` | str | `'/bin/sh'` | Shell for command execution |
| `environment` | dict | `{}` | Environment variables |

#### Job Specification

```python
job_spec = {
    'cmd': ['python', 'script.py'],           # Command to execute
    'job_name': 'my_job',                     # Job name
    'working_dir': '/path/to/workdir',        # Working directory
    'environment': {'VAR': 'value'},          # Environment variables
    'output_file': 'output.log',              # Stdout file
    'error_file': 'error.log',                # Stderr file
    'block': True                             # Wait for completion
}
```

#### Job Status Values

| Status | Description |
|--------|-------------|
| `'pending'` | Job is queued but not yet started |
| `'running'` | Job is currently executing |
| `'completed'` | Job finished successfully |
| `'failed'` | Job finished with error |
| `'cancelled'` | Job was cancelled |

#### Example Usage

```python
from molq.submitor import LocalSubmitor

# Create submitter
local = LocalSubmitor({
    'max_concurrent_jobs': 2,
    'working_directory': '/tmp/molq_jobs'
})

# Submit job
job_id = local.submit_job({
    'cmd': ['echo', 'Hello, World!'],
    'job_name': 'hello_job',
    'output_file': 'hello.out',
    'block': False
})

# Monitor job
while True:
    status = local.get_job_status(job_id)
    print(f"Job {job_id} status: {status}")
    
    if status in ['completed', 'failed', 'cancelled']:
        break
    
    time.sleep(1)

# Get job details
info = local.get_job_info(job_id)
print(f"Job info: {info}")
```

#### Methods

##### `submit_job(self, job_spec: dict) -> int`

Submit a job for local execution.

**Job Spec Parameters:**
- `cmd` (list): Command and arguments to execute
- `job_name` (str): Optional job name
- `working_dir` (str): Optional working directory
- `environment` (dict): Optional environment variables
- `output_file` (str): Optional stdout redirection file
- `error_file` (str): Optional stderr redirection file
- `block` (bool): Whether to wait for job completion

**Returns:**
- `int`: Process ID (PID) of the submitted job

##### `get_job_status(self, job_id: int) -> str`

Get the status of a local job.

**Returns:**
- `str`: One of 'pending', 'running', 'completed', 'failed', 'cancelled'

##### `get_job_info(self, job_id: int) -> dict`

Get detailed information about a local job.

**Returns:**
```python
{
    'job_id': int,
    'name': str,
    'status': str,
    'command': list,
    'working_dir': str,
    'start_time': datetime,
    'end_time': datetime,
    'exit_code': int,
    'output_file': str,
    'error_file': str
}
```

## SLURM Submitter

### SlurmSubmitor

Submitter for executing jobs on SLURM clusters.

```python
from molq.submitor import SlurmSubmitor

# Initialize
submitter = SlurmSubmitor({
    'host': 'cluster.example.com',
    'username': 'user',
    'ssh_key_path': '~/.ssh/id_rsa',
    'partition': 'compute'
})
```

#### Configuration Parameters

##### Connection Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | str | **required** | SLURM cluster hostname |
| `port` | int | `22` | SSH port |
| `username` | str | **required** | SSH username |
| `password` | str | `None` | SSH password (not recommended) |
| `ssh_key_path` | str | `~/.ssh/id_rsa` | SSH private key path |
| `ssh_key_passphrase` | str | `None` | SSH key passphrase |
| `timeout` | int | `30` | SSH connection timeout (seconds) |

##### SLURM Defaults

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `partition` | str | `None` | Default partition |
| `account` | str | `None` | Default account |
| `qos` | str | `None` | Quality of service |
| `mail_type` | str | `None` | Email notification types |
| `mail_user` | str | `None` | Email address for notifications |

#### Job Specification

```python
job_spec = {
    # Command and basic info
    'cmd': ['python', 'script.py'],
    'job_name': 'my_slurm_job',
    
    # Resource requirements
    'cpus_per_task': 4,
    'memory': '16G',
    'time': '02:00:00',
    'nodes': 1,
    'ntasks_per_node': 1,
    
    # SLURM-specific
    'partition': 'compute',
    'account': 'my_account',
    'qos': 'normal',
    'gres': 'gpu:2',
    'constraint': 'haswell',
    
    # Files and directories
    'output_file': 'job_%j.out',
    'error_file': 'job_%j.err',
    'work_dir': '/scratch/user',
    
    # Dependencies and arrays
    'dependency': 'afterok:12345',
    'array': '1-10%2',
    
    # Notifications
    'mail_type': 'END,FAIL',
    'mail_user': 'user@example.com',
    
    # Execution
    'block': False
}
```

#### Resource Specification

##### CPU and Memory

```python
# CPU specification
job_spec = {
    'cpus_per_task': 8,        # CPUs per task
    'memory': '32G',           # Total memory
    'memory_per_cpu': '4G',    # Memory per CPU
}

# Multi-node jobs
job_spec = {
    'nodes': 4,                # Number of nodes
    'ntasks_per_node': 16,     # Tasks per node
    'cpus_per_task': 1,        # CPUs per task
}
```

##### Time Limits

```python
job_spec = {
    'time': '24:00:00',        # HH:MM:SS format
    'time': '2-12:00:00',      # DD-HH:MM:SS format
}
```

##### GPU Resources

```python
job_spec = {
    'gres': 'gpu:2',           # 2 GPUs of any type
    'gres': 'gpu:tesla:4',     # 4 Tesla GPUs
    'gres': 'gpu:v100:1',      # 1 V100 GPU
}
```

##### Node Features

```python
job_spec = {
    'constraint': 'haswell',           # Intel Haswell nodes
    'constraint': 'haswell|broadwell', # Haswell OR Broadwell
    'constraint': 'bigmem&gpu',        # Big memory AND GPU
}
```

#### Job Status Values

| Status | Description |
|--------|-------------|
| `'PENDING'` | Job is waiting in queue |
| `'RUNNING'` | Job is currently executing |
| `'COMPLETED'` | Job finished successfully |
| `'FAILED'` | Job finished with error |
| `'CANCELLED'` | Job was cancelled |
| `'TIMEOUT'` | Job exceeded time limit |
| `'OUT_OF_MEMORY'` | Job ran out of memory |
| `'NODE_FAIL'` | Job failed due to node failure |

#### Example Usage

```python
from molq.submitor import SlurmSubmitor

# Create submitter
slurm = SlurmSubmitor({
    'host': 'cluster.example.com',
    'username': 'researcher',
    'partition': 'compute',
    'account': 'research_proj'
})

# Submit job
job_id = slurm.submit_job({
    'cmd': ['python', 'analysis.py'],
    'job_name': 'data_analysis',
    'cpus_per_task': 8,
    'memory': '32G',
    'time': '04:00:00',
    'output_file': 'analysis_%j.out',
    'error_file': 'analysis_%j.err',
    'block': False
})

print(f"Submitted SLURM job: {job_id}")

# Monitor job
import time
while True:
    status = slurm.get_job_status(job_id)
    print(f"Job {job_id} status: {status}")
    
    if status in ['COMPLETED', 'FAILED', 'CANCELLED']:
        break
    
    time.sleep(30)

# Get detailed job information
info = slurm.get_job_info(job_id)
print(f"Job completed in {info.get('elapsed_time', 'unknown')} time")
```

#### Methods

##### `submit_job(self, job_spec: dict) -> int`

Submit a job to SLURM.

**Returns:**
- `int`: SLURM job ID

**Raises:**
- `SubmissionError`: If sbatch command fails

##### `get_job_status(self, job_id: int) -> str`

Get SLURM job status.

**Returns:**
- `str`: SLURM job state (e.g., 'PENDING', 'RUNNING', 'COMPLETED')

##### `get_job_info(self, job_id: int) -> dict`

Get detailed SLURM job information.

**Returns:**
```python
{
    'job_id': int,
    'name': str,
    'status': str,
    'user': str,
    'partition': str,
    'account': str,
    'submit_time': str,
    'start_time': str,
    'end_time': str,
    'elapsed_time': str,
    'time_limit': str,
    'node_list': str,
    'num_nodes': int,
    'num_cpus': int,
    'memory': str,
    'exit_code': str,
    'work_dir': str
}
```

##### `cancel_job(self, job_id: int) -> bool`

Cancel a SLURM job using scancel.

**Returns:**
- `bool`: True if cancellation command succeeded

##### `get_queue_info(self) -> list`

Get information about jobs in SLURM queue.

**Returns:**
- `list[dict]`: List of job information dictionaries

##### `get_partitions(self) -> list`

Get information about available SLURM partitions.

**Returns:**
```python
[
    {
        'name': str,
        'state': str,
        'total_nodes': int,
        'available_nodes': int,
        'total_cpus': int,
        'available_cpus': int,
        'time_limit': str,
        'default': bool
    }
]
```

## Job Dependencies

### Dependency Types

SLURM supports various dependency types:

```python
job_spec = {
    'dependency': 'after:12345',        # After job 12345 starts
    'dependency': 'afterok:12345',      # After job 12345 completes successfully
    'dependency': 'afternotok:12345',   # After job 12345 fails
    'dependency': 'afterany:12345',     # After job 12345 completes (any status)
    'dependency': 'singleton',          # Only one job with this name at a time
}

# Multiple dependencies
job_spec = {
    'dependency': 'afterok:12345:12346',  # After both jobs complete
    'dependency': 'afterok:12345,afternotok:12346',  # Complex dependencies
}
```

### Job Arrays

Submit job arrays for parameter sweeps:

```python
job_spec = {
    'cmd': ['python', 'sweep.py', '$SLURM_ARRAY_TASK_ID'],
    'job_name': 'parameter_sweep',
    'array': '1-100',           # Tasks 1 through 100
    'array': '1-100%10',        # Max 10 concurrent tasks
    'array': '1,5,10,15',       # Specific task IDs
    'array': '1-10:2',          # Tasks 1,3,5,7,9 (step 2)
}
```

## Error Handling

### Exception Classes

```python
from molq.exceptions import (
    MolqError,           # Base exception
    SubmissionError,     # Job submission failed
    JobNotFoundError,    # Job ID not found
    JobExecutionError,   # Job execution failed
    ConnectionError,     # SSH/connection failed
    ConfigurationError   # Invalid configuration
)
```

### Error Handling Examples

```python
from molq.submitor import SlurmSubmitor
from molq.exceptions import SubmissionError, JobNotFoundError

try:
    submitter = SlurmSubmitor({
        'host': 'cluster.example.com',
        'username': 'user'
    })
    
    job_id = submitter.submit_job({
        'cmd': ['python', 'script.py'],
        'job_name': 'test_job',
        'cpus_per_task': 4,
        'memory': '16G',
        'time': '01:00:00'
    })
    
    print(f"Job submitted: {job_id}")
    
except SubmissionError as e:
    print(f"Failed to submit job: {e}")
    
except ConnectionError as e:
    print(f"Cannot connect to cluster: {e}")

# Check job status with error handling
try:
    status = submitter.get_job_status(job_id)
    print(f"Job status: {status}")
    
except JobNotFoundError:
    print(f"Job {job_id} not found - may have been purged")
```

## Advanced Features

### SSH Connection Pooling

```python
# Configure connection pooling for better performance
submitter = SlurmSubmitor({
    'host': 'cluster.example.com',
    'username': 'user',
    'connection_pool_size': 5,
    'keep_alive_interval': 60
})
```

### Custom SLURM Commands

```python
# Override default SLURM commands
submitter = SlurmSubmitor({
    'host': 'cluster.example.com',
    'username': 'user',
    'sbatch_command': '/usr/local/bin/sbatch',
    'squeue_command': '/usr/local/bin/squeue',
    'scancel_command': '/usr/local/bin/scancel'
})
```

### Logging and Debugging

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('molq.submitor')

# Submit job with debug logging
submitter = SlurmSubmitor({
    'host': 'cluster.example.com',
    'username': 'user',
    'debug': True
})
```

## Best Practices

### Resource Right-Sizing

```python
# Start with conservative estimates
test_job = {
    'cpus_per_task': 1,
    'memory': '2G',
    'time': '00:30:00'
}

# Scale up based on profiling
production_job = {
    'cpus_per_task': 16,
    'memory': '64G',
    'time': '12:00:00'
}
```

### Error Recovery

```python
def submit_with_retry(submitter, job_spec, max_retries=3):
    """Submit job with retry logic"""
    for attempt in range(max_retries):
        try:
            return submitter.submit_job(job_spec)
        except SubmissionError as e:
            if attempt == max_retries - 1:
                raise
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(60)  # Wait before retry
```

### Resource Monitoring

```python
def monitor_resource_usage(submitter, job_id):
    """Monitor job resource usage"""
    while True:
        try:
            info = submitter.get_job_info(job_id)
            status = info['status']
            
            if status == 'RUNNING':
                print(f"Job {job_id}:")
                print(f"  Elapsed: {info.get('elapsed_time', 'N/A')}")
                print(f"  Node(s): {info.get('node_list', 'N/A')}")
                print(f"  Memory: {info.get('memory', 'N/A')}")
            
            elif status in ['COMPLETED', 'FAILED', 'CANCELLED']:
                print(f"Job {job_id} finished: {status}")
                break
            
            time.sleep(60)
            
        except Exception as e:
            print(f"Error monitoring job: {e}")
            break
```

## Performance Considerations

### Connection Management

- Use SSH key authentication instead of passwords
- Configure connection pooling for frequent operations
- Set appropriate timeouts for network operations

### Job Submission

- Batch multiple job submissions when possible
- Use job arrays for parameter sweeps
- Set appropriate resource limits to avoid queueing delays

### Monitoring

- Use appropriate polling intervals (avoid too frequent checks)
- Implement exponential backoff for error conditions
- Cache job information when possible

## Next Steps

- Learn about [Decorators API](decorators.md)
- Explore [Core Functions](core.md)
- Check [Configuration examples](../user-guide/configuration.md)
- Review [SLURM Integration](../user-guide/slurm-integration.md) guide
