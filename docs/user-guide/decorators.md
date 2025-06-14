# Decorators

Molq provides two main decorators that transform your Python functions into job executors. This guide covers their usage, configuration options, and best practices.

## The `@cmdline` Decorator

The `@cmdline` decorator executes shell commands within your functions using a generator-based interface.

### Basic Usage

```python
from typing import Generator
from molq import cmdline

@cmdline
def simple_command() -> str:
    cp = yield {"cmd": "echo 'Hello World'", "block": True}
    return cp.stdout.decode().strip()
```

### Configuration Options

The `@cmdline` decorator accepts a dictionary with the following options:

| Option | Type | Description | Default | Required |
|--------|------|-------------|---------|----------|
| `cmd` | `str` or `List[str]` | Command to execute | - | ✓ |
| `cwd` | `str` or `Path` | Working directory | Current directory | ✗ |
| `block` | `bool` | Wait for command completion | `True` | ✗ |

### Command Formats

Commands can be specified as strings or lists:

```python
from typing import Generator
@cmdline
def string_command():
    # String format (shell will parse)
    cp = yield {"cmd": "ls -la /tmp", "block": True}
    return cp.stdout.decode()

@cmdline
def list_command():
    # List format (more secure, no shell parsing)
    cp = yield {"cmd": ["ls", "-la", "/tmp"], "block": True}
    return cp.stdout.decode()
```

### Working Directory

Specify a working directory for command execution:

```python
from typing import Generator
@cmdline
def with_working_dir():
    cp = yield {
        "cmd": ["pwd"],
        "cwd": "/tmp",
        "block": True
    }
    return cp.stdout.decode().strip()  # Returns: /tmp
```

### Blocking vs Non-Blocking

#### Blocking Execution (Default)

```python
from typing import Generator
@cmdline
def blocking_command():
    # Waits for completion, returns CompletedProcess
    cp = yield {"cmd": "sleep 2", "block": True}
    return f"Command finished with code {cp.returncode}"
```

#### Non-Blocking Execution

```python
from typing import Generator
@cmdline
def non_blocking_command():
    # Returns immediately, returns Popen object
    proc = yield {"cmd": "sleep 10", "block": False}
    return f"Started process with PID {proc.pid}"
```

## The `@submit` Decorator Factory

The `submit` function creates decorators that submit jobs to various execution backends.

### Basic Usage

```python
from typing import Generator
from molq import submit

# Create a submitter for the local machine
local = submit("local_runner", "local")

@local
def local_job() -> Generator[dict, int, int]:
    job_id = yield {
        "job_name": "my_job",
        "cmd": ["echo", "Hello from local job"],
        "block": True
    }
    return job_id
```

### Submitter Types

#### Local Submitter

```python
from typing import Generator
local = submit("my_local", "local")

@local
def local_task():
    job_id = yield {
        "job_name": "local_task",
        "cmd": ["python", "script.py"],
        "cwd": "/workspace",
        "block": True
    }
    return job_id
```

#### SLURM Submitter

```python
from typing import Generator
cluster = submit("hpc_cluster", "slurm", {
    "host": "cluster.university.edu",
    "username": "myuser",
    "key_filename": "~/.ssh/cluster_key"
})

@cluster
def cluster_job():
    job_id = yield {
        "job_name": "computation",
        "cmd": ["python", "heavy_computation.py"],
        "partition": "compute",
        "time": "02:00:00",
        "block": False  # Submit and return job ID
    }
    return job_id
```

### Job Configuration Options

Common options for job submission:

| Option | Type | Description | Default | Required |
|--------|------|-------------|---------|----------|
| `job_name` | `str` | Name of the job | Auto-generated | ✗ |
| `cmd` | `str` or `List[str]` | Command to execute | - | ✓ |
| `cwd` | `str` or `Path` | Working directory | Current directory | ✗ |
| `block` | `bool` | Wait for job completion | `True` | ✗ |
| `log_file` | `str` | Path to log file | None | ✗ |
| `env` | `dict` | Environment variables | None | ✗ |

SLURM-specific options:

| Option | Type | Description | Default |
|--------|------|-------------|---------|
| `partition` | `str` | SLURM partition | None |
| `time` | `str` | Time limit (HH:MM:SS) | None |
| `nodes` | `int` | Number of nodes | 1 |
| `ntasks` | `int` | Number of tasks | 1 |
| `cpus_per_task` | `int` | CPUs per task | 1 |
| `mem` | `str` | Memory requirement | None |

## Advanced Usage Patterns

### Error Handling

```python
from typing import Generator
@cmdline
def robust_command():
    try:
        cp = yield {"cmd": "risky_command", "block": True}
        if cp.returncode != 0:
            raise RuntimeError(f"Command failed: {cp.stderr.decode()}")
        return cp.stdout.decode()
    except Exception as e:
        return f"Error: {e}"
```

### Multiple Commands

```python
from typing import Generator
@cmdline
def multi_step_process():
    # Step 1
    cp1 = yield {"cmd": "prepare_data.py", "block": True}
    if cp1.returncode != 0:
        raise RuntimeError("Data preparation failed")
    
    # Step 2
    cp2 = yield {"cmd": "process_data.py", "block": True}
    if cp2.returncode != 0:
        raise RuntimeError("Data processing failed")
    
    return "Multi-step process completed"
```

### Environment Variables

```python
from typing import Generator
@local
def with_custom_env():
    job_id = yield {
        "cmd": ["python", "script.py"],
        "env": {
            "PYTHONPATH": "/custom/modules",
            "DATA_PATH": "/data/input",
            "OUTPUT_PATH": "/data/output"
        },
        "block": True
    }
    return job_id
```

### Dynamic Job Names

```python
from typing import Generator
from datetime import datetime

@local
def timestamped_job():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_id = yield {
        "job_name": f"data_processing_{timestamp}",
        "cmd": ["python", "process.py"],
        "block": True
    }
    return job_id
```

## Integration with Type Hints

Molq decorators preserve function signatures and work with type hints:

```python
from typing import Generator
from typing import List
import subprocess

@cmdline
def typed_command(files: List[str]) -> str:
    """Process a list of files and return summary."""
    cmd = ["wc", "-l"] + files
    cp: subprocess.CompletedProcess = yield {
        "cmd": cmd,
        "block": True
    }
    return cp.stdout.decode().strip()

# Type checking works correctly
result: str = typed_command(["file1.txt", "file2.txt"])
```

## Decorator Composition

You can combine Molq decorators with other decorators:

```python
from typing import Generator
import functools
import time

def timing_decorator(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} took {end - start:.2f} seconds")
        return result
    return wrapper

@timing_decorator
@cmdline
def timed_command():
    cp = yield {"cmd": "sleep 1", "block": True}
    return "Command completed"
```

## Custom Submitters

You can create custom submitters by extending the base classes:

```python
from typing import Generator
from molq.submitor import BaseSubmitor

class CustomSubmitor(BaseSubmitor):
    def submit_job(self, config: dict) -> Generator[dict, int, int]:
        # Custom job submission logic
        pass
    
    def get_job_status(self, job_id: int) -> str:
        # Custom status checking logic
        pass

# Register the custom submitter
custom = submit("my_custom", CustomSubmitor())
```

## Best Practices

### 1. Use Meaningful Job Names

```python
from typing import Generator
@local
def good_job_naming():
    job_id = yield {
        "job_name": f"preprocess_dataset_{dataset_name}_{version}",
        "cmd": ["python", "preprocess.py"],
        "block": True
    }
```

### 2. Validate Inputs

```python
from typing import Generator
@cmdline
def validated_command(filename: str):
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Input file {filename} not found")
    
    cp = yield {
        "cmd": ["process_file.py", filename],
        "block": True
    }
    return cp.stdout.decode()
```

### 3. Handle Resource Requirements

```python
from typing import Generator
@cluster
def resource_aware_job():
    job_id = yield {
        "job_name": "memory_intensive_task",
        "cmd": ["python", "big_computation.py"],
        "mem": "32G",
        "time": "04:00:00",
        "partition": "highmem",
        "block": False
    }
    return job_id
```

### 4. Log Important Information

```python
from typing import Generator
import logging

@local
def logged_job():
    logging.info("Starting data processing job")
    job_id = yield {
        "job_name": "data_processing",
        "cmd": ["python", "process.py"],
        "log_file": "job.log",
        "block": True
    }
    logging.info(f"Job completed with ID: {job_id}")
    return job_id
```

## Next Steps

- Learn about [Local Execution](local-execution.md) specifics
- Explore [SLURM Integration](slurm-integration.md) for cluster computing
- Check [Configuration](configuration.md) for advanced options
- See [Examples](../examples/cmdline.md) for real-world usage patterns
