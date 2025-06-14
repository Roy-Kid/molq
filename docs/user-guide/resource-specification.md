# Resource Specification

Molq provides a unified, user-friendly resource specification system that abstracts the differences between various job schedulers (SLURM, PBS, LSF, etc.). This document describes the standardized resource parameters and how they map to different scheduler systems.

## Unified Resource Parameters

### Compute Resources

| Parameter | Type | Description | Example | SLURM Equivalent |
|-----------|------|-------------|---------|------------------|
| `queue` | `str` | Target queue/partition for job execution | `"compute"`, `"gpu"`, `"highmem"` | `--partition` |
| `cpu_count` | `int` | Total number of CPU cores needed | `4`, `16`, `32` | `--ntasks` |
| `cpu_per_node` | `int` | CPU cores per compute node | `8`, `16`, `24` | `--ntasks-per-node` |
| `node_count` | `int` | Number of compute nodes required | `1`, `4`, `8` | `--nodes` |
| `memory` | `str` | Total memory requirement | `"8GB"`, `"32GB"`, `"128GB"` | `--mem` |
| `memory_per_cpu` | `str` | Memory per CPU core | `"2GB"`, `"4GB"`, `"8GB"` | `--mem-per-cpu` |
| `gpu_count` | `int` | Number of GPUs required | `1`, `2`, `4` | `--gres=gpu:N` |
| `gpu_type` | `str` | Specific GPU type | `"v100"`, `"a100"`, `"rtx3090"` | `--gres=gpu:type:N` |

### Time and Scheduling

| Parameter | Type | Description | Example | SLURM Equivalent |
|-----------|------|-------------|---------|------------------|
| `time_limit` | `str` | Maximum runtime (HH:MM:SS or human readable) | `"02:30:00"`, `"2h30m"`, `"1 day"` | `--time` |
| `priority` | `str` | Job priority level | `"low"`, `"normal"`, `"high"`, `"urgent"` | `--priority` |
| `dependency` | `str` or `list` | Job dependencies | `"job:12345"`, `["after:12345", "ok:12346"]` | `--dependency` |
| `begin_time` | `str` | Earliest start time | `"2024-12-25T10:00:00"`, `"tomorrow 9am"` | `--begin` |
| `exclusive_node` | `bool` | Request exclusive node access | `true`, `false` | `--exclusive` |

### Job Management

| Parameter | Type | Description | Example | SLURM Equivalent |
|-----------|------|-------------|---------|------------------|
| `job_name` | `str` | Human-readable job name | `"data_analysis"`, `"ml_training"` | `--job-name` |
| `output_file` | `str` | Standard output file path | `"job_%j.out"`, `"/logs/output.log"` | `--output` |
| `error_file` | `str` | Standard error file path | `"job_%j.err"`, `"/logs/error.log"` | `--error` |
| `working_dir` | `str` | Job working directory | `"/scratch/user/project"` | `--chdir` |
| `array_spec` | `str` | Array job specification | `"1-100"`, `"1-100:5"`, `"1,5,10-20"` | `--array` |

### Notification and Monitoring

| Parameter | Type | Description | Example | SLURM Equivalent |
|-----------|------|-------------|---------|------------------|
| `email` | `str` | Email address for notifications | `"user@example.com"` | `--mail-user` |
| `email_events` | `list` | Events that trigger email | `["start", "end", "fail"]` | `--mail-type` |
| `account` | `str` | Billing account | `"project123"`, `"research_group"` | `--account` |
| `comment` | `str` | Job description/comment | `"Monthly data processing"` | `--comment` |

### Advanced Options

| Parameter | Type | Description | Example | SLURM Equivalent |
|-----------|------|-------------|---------|------------------|
| `constraints` | `str` or `list` | Node feature constraints | `"intel"`, `["avx2", "infiniband"]` | `--constraint` |
| `licenses` | `str` or `list` | Software licenses required | `"matlab:2"`, `["ansys:1", "abaqus:4"]` | `--licenses` |
| `reservation` | `str` | Use specific reservation | `"maint_window"`, `"special_access"` | `--reservation` |
| `qos` | `str` | Quality of Service level | `"normal"`, `"high"`, `"debug"` | `--qos` |

## Usage Examples

### Basic Job Submission

```python
from molq import submit

# Create a SLURM submitter with resource mapping
cluster = submit("hpc_cluster", "slurm", {
    "host": "cluster.university.edu",
    "username": "researcher"
})

@cluster
def simple_computation():
    job_id = yield {
        "cmd": ["python", "compute.py"],
        "queue": "compute",           # Maps to --partition=compute
        "cpu_count": 4,              # Maps to --ntasks=4
        "memory": "8GB",             # Maps to --mem=8GB
        "time_limit": "2h",          # Maps to --time=02:00:00
        "job_name": "my_analysis",   # Maps to --job-name=my_analysis
        "block": False
    }
    return job_id
```

### GPU Job with Advanced Resources

```python
@cluster
def gpu_training():
    job_id = yield {
        "cmd": ["python", "train_model.py"],
        "queue": "gpu",
        "gpu_count": 2,
        "gpu_type": "v100",
        "cpu_count": 16,
        "memory_per_cpu": "4GB",
        "time_limit": "12h",
        "job_name": "model_training",
        "email": "researcher@university.edu",
        "email_events": ["end", "fail"],
        "output_file": "training_%j.out",
        "error_file": "training_%j.err",
        "block": False
    }
    return job_id
```

### High Memory Job

```python
@cluster
def memory_intensive_job():
    job_id = yield {
        "cmd": ["./large_analysis", "input.dat"],
        "queue": "highmem",
        "node_count": 1,
        "memory": "256GB",
        "cpu_count": 32,
        "time_limit": "24h",
        "exclusive_node": True,
        "job_name": "large_memory_analysis",
        "account": "research_project_123",
        "block": False
    }
    return job_id
```

### Array Job

```python
@cluster
def parameter_sweep():
    job_id = yield {
        "cmd": ["python", "sweep.py", "${MOLQ_ARRAY_TASK_ID}"],
        "queue": "compute",
        "cpu_count": 2,
        "memory": "4GB",
        "time_limit": "1h",
        "array_spec": "1-100",       # Run 100 array tasks
        "job_name": "param_sweep",
        "output_file": "sweep_%A_%a.out",
        "error_file": "sweep_%A_%a.err",
        "block": False
    }
    return job_id
```

### Job with Dependencies

```python
@cluster
def dependent_job():
    # First job
    preprocess_id = yield {
        "cmd": ["python", "preprocess.py"],
        "queue": "compute", 
        "cpu_count": 4,
        "memory": "8GB",
        "time_limit": "30m",
        "job_name": "preprocess_data",
        "block": False
    }
    
    # Second job depends on first
    analysis_id = yield {
        "cmd": ["python", "analyze.py"],
        "queue": "compute",
        "cpu_count": 8,
        "memory": "16GB", 
        "time_limit": "2h",
        "dependency": f"ok:{preprocess_id}",  # Wait for successful completion
        "job_name": "analyze_data",
        "block": False
    }
    
    return [preprocess_id, analysis_id]
```

## Scheduler Mapping

### SLURM Mapping

The unified parameters map to SLURM options as follows:

```python
SLURM_MAPPING = {
    "queue": "--partition",
    "cpu_count": "--ntasks",
    "cpu_per_node": "--ntasks-per-node", 
    "node_count": "--nodes",
    "memory": "--mem",
    "memory_per_cpu": "--mem-per-cpu",
    "time_limit": "--time",
    "job_name": "--job-name",
    "output_file": "--output",
    "error_file": "--error",
    "working_dir": "--chdir",
    "email": "--mail-user",
    "email_events": "--mail-type",
    "account": "--account",
    "priority": "--priority",
    "exclusive_node": "--exclusive",
    "array_spec": "--array",
    "constraints": "--constraint",
    "licenses": "--licenses",
    "reservation": "--reservation",
    "qos": "--qos",
    "dependency": "--dependency",
    "begin_time": "--begin",
    "comment": "--comment"
}
```

### PBS/Torque Mapping

```python
PBS_MAPPING = {
    "queue": "-q",
    "cpu_count": "-l ppn",  # Combined with nodes
    "node_count": "-l nodes",
    "memory": "-l mem",
    "time_limit": "-l walltime",
    "job_name": "-N",
    "output_file": "-o",
    "error_file": "-e", 
    "working_dir": "-d",
    "email": "-M",
    "email_events": "-m",
    "account": "-A",
    "priority": "-p",
    "array_spec": "-t",
    "dependency": "-W depend"
}
```

### LSF Mapping

```python
LSF_MAPPING = {
    "queue": "-q",
    "cpu_count": "-n", 
    "memory": "-M",
    "time_limit": "-W",
    "job_name": "-J",
    "output_file": "-o",
    "error_file": "-e",
    "working_dir": "-cwd",
    "email": "-u",
    "email_events": "-B,-N",  # Begin and end notifications
    "account": "-P",
    "exclusive_node": "-x",
    "array_spec": "-J name[array_spec]",
    "dependency": "-w"
}
```

## Human-Readable Time Formats

Molq supports various time format inputs that are automatically converted:

```python
# Standard format
"02:30:00"      # 2 hours 30 minutes

# Human readable
"2h30m"         # 2 hours 30 minutes  
"90m"           # 90 minutes
"1.5h"          # 1.5 hours
"3600s"         # 3600 seconds
"1 day"         # 24 hours
"2 days 4h"     # 52 hours
"1w"            # 1 week (168 hours)
```

## Memory Format Support

```python
# Bytes
"1073741824"    # 1GB in bytes

# Human readable
"1GB"           # 1 gigabyte
"512MB"         # 512 megabytes  
"2TB"           # 2 terabytes
"4.5GB"         # 4.5 gigabytes
"1024MB"        # 1024 megabytes
```

## Email Event Types

Standardized email notification events:

```python
EMAIL_EVENTS = {
    "start": "Job started",
    "end": "Job completed (success or failure)",
    "fail": "Job failed", 
    "success": "Job completed successfully",
    "timeout": "Job exceeded time limit",
    "cancel": "Job was cancelled",
    "requeue": "Job was requeued",
    "all": "All events"
}
```

## Priority Levels

Human-readable priority levels:

```python
PRIORITY_LEVELS = {
    "urgent": 1000,
    "high": 750,
    "normal": 500,    # Default
    "low": 250,
    "idle": 100
}
```

## Best Practices

### 1. Resource Estimation

```python
# Start conservative, then scale up
@cluster  
def initial_test():
    job_id = yield {
        "cmd": ["python", "test_job.py"],
        "queue": "debug",        # Use debug queue for testing
        "cpu_count": 1,
        "memory": "2GB", 
        "time_limit": "10m",     # Short time for testing
        "job_name": "resource_test"
    }
```

### 2. Use Appropriate Queues

```python
# Choose queue based on requirements
job_configs = {
    "quick_analysis": {
        "queue": "express",      # Fast queue for short jobs
        "time_limit": "30m"
    },
    "large_computation": {
        "queue": "compute",      # Standard compute queue  
        "time_limit": "24h"
    },
    "gpu_training": {
        "queue": "gpu",          # GPU-enabled queue
        "gpu_count": 2
    },
    "memory_intensive": {
        "queue": "highmem",      # High memory queue
        "memory": "128GB"
    }
}
```

### 3. Efficient Resource Usage

```python
# Match resources to actual needs
@cluster
def optimized_job():
    job_id = yield {
        "cmd": ["python", "parallel_job.py"],
        "cpu_count": 16,         # Match to actual parallelism
        "memory_per_cpu": "2GB", # More efficient than total memory
        "time_limit": "4h",      # Realistic time estimate
        "exclusive_node": False  # Share nodes when possible
    }
```

## Error Handling

```python
from molq.exceptions import ResourceError, SchedulerError

@cluster
def robust_job():
    try:
        job_id = yield {
            "cmd": ["python", "analysis.py"],
            "cpu_count": 32,
            "memory": "64GB",
            "time_limit": "8h",
            "queue": "compute"
        }
        return job_id
    except ResourceError as e:
        # Handle resource specification errors
        print(f"Resource error: {e}")
        # Retry with reduced resources
        job_id = yield {
            "cmd": ["python", "analysis.py"],
            "cpu_count": 16,
            "memory": "32GB", 
            "time_limit": "12h",
            "queue": "compute"
        }
        return job_id
    except SchedulerError as e:
        # Handle scheduler-specific errors
        print(f"Scheduler error: {e}")
        raise
```

## Next Steps

- Learn about [SLURM Integration](slurm-integration.md) for cluster-specific details
- See [Configuration](configuration.md) for system-wide resource defaults
- Check [Examples](../examples/slurm-jobs.md) for real-world usage patterns
- Review [API Reference](../api/submitters.md) for implementation details
