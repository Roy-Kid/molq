# SLURM Integration

Molq provides seamless integration with SLURM (Simple Linux Utility for Resource Management) clusters, allowing you to submit and manage jobs on high-performance computing systems.

## Overview

The SLURM integration allows you to:

- Submit jobs to SLURM clusters with user-friendly resource specifications
- Monitor job status and progress
- Handle job dependencies
- Configure resource requirements using unified parameters
- Manage job queues and partitions

## Unified Resource Specification

Molq provides a **unified resource specification system** that abstracts SLURM's complex parameter syntax into user-friendly names. This system automatically maps your resource requirements to the appropriate SLURM parameters.

### Key Benefits

- **User-friendly names**: Use intuitive parameter names like `cpu_count` instead of `--ntasks`
- **Automatic conversion**: Time and memory formats are automatically converted
- **Cross-platform compatibility**: Same specification works across different schedulers
- **Type safety**: Full type hints and validation

### Quick Example

```python
from typing import Generator
from molq import submit

cluster = submit('hpc', 'slurm', {
    'host': 'cluster.university.edu',
    'username': 'researcher'
})

@cluster
def my_analysis():
    job_id = yield {
        # Unified resource specification - no SLURM syntax needed!
        "queue": "compute",           # Maps to --partition=compute
        "cpu_count": 16,             # Maps to --ntasks=16
        "memory": "32GB",            # Maps to --mem=32G
        "time_limit": "4h30m",       # Maps to --time=04:30:00
        "job_name": "data_analysis", # Maps to --job-name=data_analysis
        "email": "user@university.edu",
        "email_events": ["end", "fail"],
        "cmd": ["python", "analysis.py"],
        "block": False
    }
    return job_id
```

For complete details, see the [Resource Specification](resource-specification.md) guide.

## Setting Up SLURM Integration

### Basic Configuration

```python title="slurm_setup.py"
from typing import Generator
from molq import submit

# Configure SLURM cluster connection
slurm_cluster = submit('my_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'your_username',
    'ssh_key_path': '~/.ssh/id_rsa',
    'partition': 'compute',
    'account': 'your_account'
})
```

### SSH Key Setup

For passwordless authentication, set up SSH keys:

```bash
# Generate SSH key pair (if not already done)
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# Copy public key to cluster
ssh-copy-id your_username@cluster.example.com
```

## Job Submission

### Basic Job Submission

```python title="basic_slurm_job.py"
from typing import Generator
from molq import submit

slurm = submit('hpc_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'user',
    'partition': 'compute'
})

@slurm
def run_simulation() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'simulation.py'],
        'job_name': 'my_simulation',
        'output_file': 'simulation_%j.out',
        'error_file': 'simulation_%j.err',
        'cpus_per_task': 4,
        'memory': '8G',
        'time': '02:00:00',
        'block': False
    }
    return job_id
```

### Advanced Job Configuration

```python title="advanced_slurm.py"
from typing import Generator
@slurm
def advanced_job() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['mpirun', '-n', '16', './my_program'],
        'job_name': 'mpi_job',
        'partition': 'mpi',
        'nodes': 2,
        'ntasks_per_node': 8,
        'cpus_per_task': 1,
        'memory_per_cpu': '2G',
        'time': '24:00:00',
        'gres': 'gpu:2',
        'constraint': 'haswell',
        'mail_type': 'END,FAIL',
        'mail_user': 'user@example.com',
        'block': False
    }
    return job_id
```

## Job Parameters

### Resource Specifications

| Parameter | Description | Example |
|-----------|-------------|---------|
| `cpus_per_task` | CPU cores per task | `4` |
| `memory` | Memory per node | `'16G'` |
| `memory_per_cpu` | Memory per CPU | `'2G'` |
| `nodes` | Number of nodes | `2` |
| `ntasks_per_node` | Tasks per node | `8` |
| `time` | Wall clock time limit | `'02:30:00'` |

### SLURM-Specific Options

| Parameter | Description | Example |
|-----------|-------------|---------|
| `partition` | Queue/partition name | `'compute'` |
| `account` | Billing account | `'project123'` |
| `qos` | Quality of Service | `'normal'` |
| `gres` | Generic resources | `'gpu:2'` |
| `constraint` | Node features | `'haswell'` |

### File Management

| Parameter | Description | Example |
|-----------|-------------|---------|
| `output_file` | Standard output file | `'job_%j.out'` |
| `error_file` | Standard error file | `'job_%j.err'` |
| `work_dir` | Working directory | `'/scratch/user/job'` |

## Job Monitoring

### Checking Job Status

```python title="monitor_jobs.py"
from typing import Generator
from molq.submitor import SlurmSubmitor

# Initialize SLURM submitter directly for monitoring
submitter = SlurmSubmitor({
    'host': 'cluster.example.com',
    'username': 'user'
})

# Check job status
job_id = 12345
status = submitter.get_job_status(job_id)
print(f"Job {job_id} status: {status}")

# Get job info
job_info = submitter.get_job_info(job_id)
print(f"Job details: {job_info}")
```

### Queue Information

```python title="queue_info.py"
from typing import Generator
# Check queue status
queue_info = submitter.get_queue_info()
print("Queue status:")
for job in queue_info:
    print(f"Job {job['job_id']}: {job['status']} - {job['name']}")

# Check available partitions
partitions = submitter.get_partitions()
print("Available partitions:")
for partition in partitions:
    print(f"- {partition['name']}: {partition['state']}")
```

## Error Handling

### Common Issues and Solutions

```python title="error_handling.py"
from typing import Generator
import logging
from molq import submit

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

slurm = submit('cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'user',
    'timeout': 30  # SSH timeout in seconds
})

@slurm
def robust_job() -> Generator[dict, int, int]:
    try:
        job_id = yield {
            'cmd': ['python', 'script.py'],
            'job_name': 'robust_job',
            'time': '01:00:00',
            'memory': '4G',
            'block': False
        }
        return job_id
    except Exception as e:
        logging.error(f"Job submission failed: {e}")
        raise
```

### Troubleshooting Tips

!!! tip "Connection Issues"
    - Verify SSH connectivity: `ssh username@cluster.example.com`
    - Check SSH key permissions: `chmod 600 ~/.ssh/id_rsa`
    - Ensure cluster hostname is resolvable

!!! warning "Resource Limits"
    - Check partition limits with `sinfo`
    - Verify account permissions with `sacctmgr show user $USER`
    - Monitor resource usage with `squeue -u $USER`

!!! note "Job Failures"
    - Check SLURM error files (*.err)
    - Review job output files (*.out)
    - Use `scontrol show job <job_id>` for detailed info

## Best Practices

### Resource Estimation

```python title="resource_estimation.py"
from typing import Generator
# Start with conservative estimates
@slurm
def test_resources() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'benchmark.py'],
        'job_name': 'resource_test',
        'cpus_per_task': 1,
        'memory': '1G',
        'time': '00:30:00',
        'block': True
    }
    return job_id

# Scale up based on results
@slurm  
def production_job() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'production.py'],
        'job_name': 'production',
        'cpus_per_task': 8,
        'memory': '32G',
        'time': '12:00:00',
        'block': False
    }
    return job_id
```

### Job Dependencies

```python title="job_dependencies.py"
from typing import Generator
@slurm
def preprocessing() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'preprocess.py'],
        'job_name': 'preprocess',
        'time': '01:00:00',
        'block': False
    }
    return job_id

@slurm
def analysis(prep_job_id: int) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'analyze.py'],
        'job_name': 'analysis',
        'dependency': f'afterok:{prep_job_id}',
        'time': '04:00:00',
        'block': False
    }
    return job_id
```

## Integration with Hamilton

```python title="hamilton_slurm.py"
from typing import Generator
import hamilton.driver
from molq import submit

# SLURM cluster configuration
hpc = submit('hpc', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'user',
    'partition': 'compute'
})

# Hamilton dataflow with SLURM jobs
@hpc
def data_processing(input_file: str) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'process_data.py', input_file],
        'job_name': 'data_processing',
        'cpus_per_task': 4,
        'memory': '16G',
        'time': '02:00:00',
        'block': True
    }
    return job_id

@hpc
def analysis(processing_job_id: int) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'analyze.py'],
        'job_name': 'analysis',
        'dependency': f'afterok:{processing_job_id}',
        'cpus_per_task': 8,
        'memory': '32G',
        'time': '04:00:00',
        'block': False
    }
    return job_id

# Execute with Hamilton
if __name__ == "__main__":
    dr = hamilton.driver.Driver({}, data_processing, analysis)
    results = dr.execute(['analysis'], inputs={'input_file': 'data.csv'})
    print(f"Analysis job ID: {results['analysis']}")
```

## Next Steps

- Learn about [Configuration](configuration.md) options
- Explore [Examples](../examples/slurm-jobs.md) for common patterns
- Check the [API Reference](../api/submitters.md) for detailed documentation
