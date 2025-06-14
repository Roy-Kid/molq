# Resource Specification Examples

This document provides practical examples of using Molq's unified resource specification system across different job types and scenarios.

## Basic Usage

### Simple Compute Job

```python
from typing import Generator
from molq import submit

# Setup cluster connection
cluster = submit("hpc", "slurm", {
    "host": "cluster.university.edu",
    "username": "researcher"
})

@cluster
def basic_analysis():
    """Run a basic data analysis job."""
    job_id = yield {
        "cmd": ["python", "analyze_data.py"],
        
        # Resource specification using friendly names
        "queue": "compute",           # Instead of --partition
        "cpu_count": 8,              # Instead of --ntasks  
        "memory": "16GB",            # Instead of --mem
        "time_limit": "2h30m",       # Instead of --time
        "job_name": "data_analysis", # Instead of --job-name
        
        "block": False
    }
    return job_id

# Submit the job
job_id = basic_analysis()
print(f"Submitted job: {job_id}")
```

## Advanced Examples

### GPU Machine Learning Job

```python
from typing import Generator
@cluster
def gpu_training():
    """Train a deep learning model on GPUs."""
    job_id = yield {
        "cmd": ["python", "train_model.py", "--epochs", "100"],
        
        # GPU resources
        "queue": "gpu",
        "gpu_count": 4,
        "gpu_type": "v100",          # Specific GPU type
        
        # CPU and memory
        "cpu_count": 32,
        "memory_per_cpu": "4GB",     # More flexible than total memory
        
        # Time and priority
        "time_limit": "2d12h",       # 2 days 12 hours
        "priority": "high",          # Human-readable priority
        
        # Job management
        "job_name": "bert_training",
        "output_file": "training_%j.out",
        "error_file": "training_%j.err",
        
        # Notifications
        "email": "researcher@university.edu",
        "email_events": ["end", "fail"],
        
        # Billing
        "account": "deep_learning_project",
        
        "block": False
    }
    return job_id
```

### High Memory Bioinformatics Job

```python
from typing import Generator
@cluster
def genome_assembly():
    """Assemble a large genome requiring high memory."""
    job_id = yield {
        "cmd": ["./assembler", "--input", "reads.fastq", "--output", "assembly.fasta"],
        
        # High memory requirements
        "queue": "highmem",
        "memory": "512GB",           # Large memory requirement
        "cpu_count": 64,
        "exclusive_node": True,      # Need exclusive access
        
        # Long runtime
        "time_limit": "1w",          # 1 week
        
        # Advanced options
        "constraints": ["intel", "infiniband"],  # Node requirements
        "licenses": ["bioinformatics:1"],        # Software licenses
        
        "job_name": "genome_assembly_hg38",
        "comment": "Human genome assembly for project XYZ",
        
        "block": False
    }
    return job_id
```

### Parameter Sweep Array Job

```python
from typing import Generator
@cluster
def parameter_sweep():
    """Run parameter sweep with array jobs."""
    job_id = yield {
        "cmd": ["python", "sweep.py", "--param", "${SLURM_ARRAY_TASK_ID}"],
        
        # Array job specification
        "array_spec": "1-1000:10",   # 100 tasks (1, 11, 21, ..., 991)
        
        # Resources per task
        "queue": "compute",
        "cpu_count": 2,
        "memory": "4GB",
        "time_limit": "30m",
        
        # File naming with array variables
        "job_name": "param_sweep",
        "output_file": "sweep_%A_%a.out",  # %A = job ID, %a = array index
        "error_file": "sweep_%A_%a.err",
        
        "block": False
    }
    return job_id
```

### Job with Dependencies

```python
from typing import Generator
@cluster
def preprocessing_pipeline():
    """Run a multi-stage data processing pipeline."""
    
    # Stage 1: Data preprocessing
    preprocess_id = yield {
        "cmd": ["python", "preprocess.py", "raw_data.csv"],
        "queue": "compute",
        "cpu_count": 8,
        "memory": "32GB",
        "time_limit": "1h",
        "job_name": "preprocess_data",
        "output_file": "preprocess.out",
        "block": False
    }
    
    # Stage 2: Analysis (depends on preprocessing)
    analysis_id = yield {
        "cmd": ["python", "analyze.py", "processed_data.csv"],
        "queue": "compute", 
        "cpu_count": 16,
        "memory": "64GB",
        "time_limit": "4h",
        "job_name": "analyze_data",
        "dependency": f"ok:{preprocess_id}",  # Wait for successful completion
        "output_file": "analysis.out",
        "block": False
    }
    
    # Stage 3: Visualization (depends on analysis)
    viz_id = yield {
        "cmd": ["python", "visualize.py", "analysis_results.json"],
        "queue": "compute",
        "cpu_count": 4,
        "memory": "16GB", 
        "time_limit": "30m",
        "job_name": "create_plots",
        "dependency": f"ok:{analysis_id}",
        "output_file": "visualization.out",
        "block": False
    }
    
    return [preprocess_id, analysis_id, viz_id]
```

## Time Format Examples

Molq supports various human-readable time formats:

```python
from typing import Generator
# Different ways to specify time limits
time_examples = {
    "30_minutes": "30m",
    "2_hours": "2h", 
    "2_hours_30_minutes": "2h30m",
    "half_day": "12h",
    "one_day": "1d",
    "one_week": "1w",
    "mixed_format": "2d4h30m",
    "decimal_hours": "1.5h",
    "traditional": "02:30:00"
}

@cluster
def time_format_demo():
    """Demonstrate different time formats."""
    job_id = yield {
        "cmd": ["sleep", "10"],
        "queue": "debug",
        "cpu_count": 1,
        "memory": "1GB",
        "time_limit": "15m",  # Any of the formats above work
        "job_name": "time_demo",
        "block": True
    }
    return job_id
```

## Memory Format Examples

Various memory specification formats are supported:

```python
from typing import Generator
# Different ways to specify memory
memory_examples = {
    "gigabytes": "8GB",
    "megabytes": "512MB", 
    "terabytes": "2TB",
    "decimal": "4.5GB",
    "lowercase": "16gb",
    "bytes": "1073741824"  # 1GB in bytes
}

@cluster
def memory_format_demo():
    """Demonstrate different memory formats."""
    job_id = yield {
        "cmd": ["python", "memory_test.py"],
        "queue": "compute",
        "cpu_count": 4,
        "memory": "8GB",  # Any of the formats above work
        "time_limit": "1h",
        "job_name": "memory_demo",
        "block": True
    }
    return job_id
```

## Priority and Quality of Service

```python
from typing import Generator
@cluster
def priority_demo():
    """Demonstrate priority levels."""
    # High priority job
    urgent_id = yield {
        "cmd": ["python", "urgent_analysis.py"],
        "queue": "compute",
        "cpu_count": 16,
        "memory": "32GB",
        "time_limit": "2h",
        "priority": "urgent",  # or "high", "normal", "low", "idle"
        "qos": "premium",      # Quality of Service
        "job_name": "urgent_work",
        "block": False
    }
    
    # Low priority background job
    background_id = yield {
        "cmd": ["python", "background_task.py"],
        "queue": "compute",
        "cpu_count": 4,
        "memory": "8GB",
        "time_limit": "24h",
        "priority": "idle",    # Run when resources available
        "job_name": "background_work",
        "block": False
    }
    
    return [urgent_id, background_id]
```

## Cross-Platform Compatibility

The same resource specification works across different schedulers:

```python
from typing import Generator
# Same code works with different schedulers
def create_job_spec():
    """Create a job specification that works across schedulers."""
    return {
        "cmd": ["python", "portable_job.py"],
        "queue": "compute",
        "cpu_count": 8,
        "memory": "16GB",
        "time_limit": "2h",
        "job_name": "portable_job",
        "email": "user@example.com",
        "email_events": ["end", "fail"]
    }

# Use with SLURM
slurm_cluster = submit("slurm_cluster", "slurm", {
    "host": "slurm.cluster.edu",
    "username": "user"
})

# Use with PBS
pbs_cluster = submit("pbs_cluster", "pbs", {
    "host": "pbs.cluster.edu", 
    "username": "user"
})

# Same job specification for both
job_spec = create_job_spec()

@slurm_cluster
def slurm_job():
    job_id = yield job_spec
    return job_id

@pbs_cluster  
def pbs_job():
    job_id = yield job_spec  # Same specification!
    return job_id
```

## Error Handling and Validation

```python
from typing import Generator
from molq.exceptions import ResourceError

@cluster
def robust_job():
    """Demonstrate error handling with resource specifications."""
    try:
        job_id = yield {
            "cmd": ["python", "big_job.py"],
            "queue": "compute",
            "cpu_count": 128,      # Large request
            "memory": "1TB",       # Might be too much
            "time_limit": "7d",    # Very long
            "job_name": "ambitious_job",
            "block": False
        }
        return job_id
    
    except ResourceError as e:
        print(f"Resource request failed: {e}")
        
        # Retry with more modest requirements
        job_id = yield {
            "cmd": ["python", "big_job.py", "--reduced-mode"],
            "queue": "compute", 
            "cpu_count": 32,       # Reduced request
            "memory": "128GB",     # More reasonable
            "time_limit": "2d",    # Shorter time
            "job_name": "modest_job",
            "block": False
        }
        return job_id
```

## Best Practices

### 1. Start Small and Scale Up

```python
from typing import Generator
@cluster
def iterative_development():
    """Start with small jobs for testing."""
    # Development/testing job
    if os.getenv("MOLQ_ENV") == "development":
        job_spec = {
            "queue": "debug",      # Fast queue for testing
            "cpu_count": 1,
            "memory": "2GB",
            "time_limit": "10m",   # Short time for quick feedback
            "job_name": "dev_test"
        }
    else:
        # Production job
        job_spec = {
            "queue": "compute",
            "cpu_count": 32,
            "memory": "128GB", 
            "time_limit": "12h",
            "job_name": "production_run"
        }
    
    job_spec["cmd"] = ["python", "my_job.py"]
    job_id = yield job_spec
    return job_id
```

### 2. Use Resource Templates

```python
from typing import Generator
# Define common resource templates
RESOURCE_TEMPLATES = {
    "small_job": {
        "queue": "compute",
        "cpu_count": 4,
        "memory": "8GB",
        "time_limit": "2h"
    },
    "medium_job": {
        "queue": "compute", 
        "cpu_count": 16,
        "memory": "64GB",
        "time_limit": "8h"
    },
    "large_job": {
        "queue": "compute",
        "cpu_count": 64,
        "memory": "256GB",
        "time_limit": "24h"
    },
    "gpu_job": {
        "queue": "gpu",
        "gpu_count": 2,
        "cpu_count": 16,
        "memory": "32GB",
        "time_limit": "12h"
    }
}

@cluster
def template_job(template_name: str, cmd: List[str]):
    """Use predefined resource templates."""
    spec = RESOURCE_TEMPLATES[template_name].copy()
    spec.update({
        "cmd": cmd,
        "job_name": f"{template_name}_job",
        "block": False
    })
    
    job_id = yield spec
    return job_id

# Usage
job_id = template_job("medium_job", ["python", "analysis.py"])
```

### 3. Environment-Specific Configuration

```python
from typing import Generator
import os

@cluster
def environment_aware_job():
    """Adjust resources based on environment."""
    # Base configuration
    spec = {
        "cmd": ["python", "adaptive_job.py"],
        "queue": "compute",
        "job_name": "adaptive_job"
    }
    
    # Adjust based on data size
    data_size = os.path.getsize("input_data.csv") / (1024**3)  # GB
    
    if data_size < 1:  # Small data
        spec.update({
            "cpu_count": 4,
            "memory": "8GB",
            "time_limit": "1h"
        })
    elif data_size < 10:  # Medium data
        spec.update({
            "cpu_count": 16, 
            "memory": "32GB",
            "time_limit": "4h"
        })
    else:  # Large data
        spec.update({
            "cpu_count": 32,
            "memory": "128GB",
            "time_limit": "12h"
        })
    
    job_id = yield spec
    return job_id
```

## Integration with Hamilton

Molq's resource specification integrates seamlessly with Hamilton dataflows:

```python
from typing import Generator
import pandas as pd
from hamilton import driver

# Hamilton nodes with Molq decorators
def load_data() -> pd.DataFrame:
    """Load input data."""
    return pd.read_csv("data.csv")

@cluster
def process_data(load_data: pd.DataFrame) -> Generator[dict, int, int]:
    """Process data using cluster resources."""
    # Save data for cluster job
    load_data.to_csv("cluster_input.csv", index=False)
    
    job_id = yield {
        "cmd": ["python", "cluster_process.py", "cluster_input.csv"],
        "queue": "compute",
        "cpu_count": 16,
        "memory": "32GB",
        "time_limit": "4h",
        "job_name": "data_processing",
        "block": True  # Wait for completion
    }
    return job_id

def load_results(process_data: int) -> pd.DataFrame:
    """Load results from cluster job."""
    return pd.read_csv("cluster_output.csv")

# Create Hamilton driver
dr = driver.Driver({}, load_data, process_data, load_results)

# Execute workflow
results = dr.execute(["load_results"])
```

## Next Steps

- See [SLURM Integration](../user-guide/slurm-integration.md) for SLURM-specific details
- Check [Configuration](../user-guide/configuration.md) for system-wide settings
- Review [API Reference](../api/submitters.md) for implementation details
- Explore [Monitoring](monitoring.md) for job status tracking
