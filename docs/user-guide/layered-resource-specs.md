# Molq Layered Resource Specification System

## Overview

Molq's new resource specification system is designed based on Pydantic, using a layered abstraction approach that supports everything from simple local execution to complex cluster jobs.

## Layered Design

### 1. BaseResourceSpec - Basic Specification
Suitable for **local execution**, providing the most basic parameters:

```python
from molq.resources import BaseResourceSpec

# Local execution example
spec = BaseResourceSpec(
    cmd="python train.py",
    workdir="/tmp/workspace",          # Working directory
    env={"CUDA_VISIBLE_DEVICES": "0"}, # Environment variables
    job_name="local_training",         # Job name
    output_file="output.log",          # Output file
    error_file="error.log"             # Error file
)
```

### 2. ComputeResourceSpec - Compute Specification
Inherits from basic specification, adds **CPU, memory, time** and other compute resources:

```python
from molq.resources import ComputeResourceSpec

# Compute job example
spec = ComputeResourceSpec(
    cmd="python train.py --epochs 100",
    cpu_count=8,                       # CPU core count
    memory="16GB",                     # Memory size
    time_limit="4h30m",                # Time limit
    job_name="compute_training",
    workdir="/home/user/project"
)
```

### 3. ClusterResourceSpec - Cluster Specification
Inherits from compute specification, adds **queue, node, GPU, priority** and other cluster features:

```python
from molq.resources import ClusterResourceSpec, PriorityLevel, EmailEvent

# Cluster job example
spec = ClusterResourceSpec(
    cmd=["python", "distributed_train.py"],
    queue="gpu",                       # Queue/partition
    node_count=2,                      # Node count
    cpu_per_node=16,                   # CPUs per node
    memory="64GB",                     # Total memory
    gpu_count=4,                       # GPU count
    gpu_type="v100",                   # GPU type
    time_limit="12h",                  # Time limit
    priority=PriorityLevel.HIGH,       # Priority
    email="user@example.com",          # Email notification
    email_events=[EmailEvent.START, EmailEvent.END],
    account="research_group",          # Billing account
    exclusive_node=True,               # Exclusive node
    constraints=["intel", "infiniband"] # Node constraints
)
```

## Convenience Functions

### Quick creation of common job types:

```python
from molq.resources import (
    create_compute_job, create_gpu_job, 
    create_array_job, create_high_memory_job
)

# Compute job
compute_job = create_compute_job(
    cmd="python analysis.py",
    cpu_count=4,
    memory="8GB",
    time_limit="2h"
)

# GPU job
gpu_job = create_gpu_job(
    cmd="python gpu_train.py",
    gpu_count=2,
    gpu_type="a100",
    cpu_count=8,
    memory="32GB",
    time_limit="8h"
)

# Array job
array_job = create_array_job(
    cmd="python batch_process.py --task $SLURM_ARRAY_TASK_ID",
    array_spec="1-100:5",  # 1 to 100, step 5
    cpu_count=1,
    memory="2GB",
    time_limit="30m"
)

# High memory job
highmem_job = create_high_memory_job(
    cmd="python big_data_analysis.py",
    memory="256GB",
    cpu_count=32,
    time_limit="24h"
)
```

## Scheduler Mapping

### Automatic mapping to different schedulers:

```python
from molq.resources import ResourceManager

# Create specification
spec = ClusterResourceSpec(
    cmd="python example.py",
    queue="gpu",
    cpu_count=8,
    memory="16GB",
    gpu_count=1,
    gpu_type="v100"
)

# Map to SLURM
slurm_params = ResourceManager.map_to_scheduler(spec, "slurm")
# Output: {'--partition': 'gpu', '--ntasks': '8', '--mem': '16G', '--gres': 'gpu:v100:1'}

# Map to PBS
pbs_params = ResourceManager.map_to_scheduler(spec, "pbs")
# Output: {'-q': 'gpu', '-l nodes': '1:ppn=8', '-l mem': '16gb'}

# Format as command line arguments
slurm_args = ResourceManager.format_command_args(spec, "slurm")
# Output: ['--partition', 'gpu', '--ntasks', '8', '--mem', '16G', '--gres', 'gpu:v100:1']
```

## Parameter Validation

The system automatically validates parameter formats and consistency:

```python
# ✓ Time format support:
"2h30m", "02:30:00", "1d", "90m"

# ✓ Memory format support:
"8GB", "512MB", "2TB", "4.5GB"

# ✗ Automatic error detection:
ClusterResourceSpec(
    cmd="test",
    gpu_type="v100"  # Error: GPU type specified but no count
)
# ValueError: gpu_type specified but gpu_count is not set

ClusterResourceSpec(
    cmd="test", 
    cpu_count=16,
    cpu_per_node=8,
    node_count=3  # Error: 8*3=24 != 16
)
# ValueError: cpu_count doesn't match cpu_per_node * node_count
```

## Human-Readable Formats

Supports intuitive time and memory representations:

```python
# Time formats
time_limit="2h30m"     # 2 hours 30 minutes
time_limit="1d4h"      # 1 day 4 hours  
time_limit="90m"       # 90 minutes
time_limit="02:30:00"  # HH:MM:SS format

# Memory formats
memory="8GB"           # 8 gigabytes
memory="512MB"         # 512 megabytes
memory="2.5TB"         # 2.5 terabytes
memory_per_cpu="4GB"   # 4GB per CPU
```

## Alias Support

Provides aliases for common parameters:

```python
# workdir and cwd are equivalent
BaseResourceSpec(cmd="test", workdir="/tmp")
BaseResourceSpec(cmd="test", cwd="/tmp")

# queue and partition are equivalent
ClusterResourceSpec(cmd="test", queue="gpu")
ClusterResourceSpec(cmd="test", partition="gpu")
```

## Extensibility

Based on Pydantic, easily extensible:

```python
class CustomResourceSpec(ClusterResourceSpec):
    """Custom specification with specific fields"""
    custom_param: Optional[str] = None
    special_requirement: bool = False
    
    @field_validator('custom_param')
    @classmethod
    def validate_custom(cls, v):
        # Custom validation logic
        return v
```

## Best Practices

1. **Local development**: Use `BaseResourceSpec`
2. **Single-machine compute**: Use `ComputeResourceSpec`  
3. **Cluster jobs**: Use `ClusterResourceSpec`
4. **Quick creation**: Use convenience functions (`create_*_job`)
5. **Parameter validation**: Leverage automatic validation to avoid errors
6. **Readability**: Use human-readable time/memory formats
7. **Compatibility**: Adapt to different schedulers through `ResourceManager`

This layered design ensures both ease of use for simple scenarios and complete functionality for complex scenarios!
