# Basic Concepts

Understanding the core concepts behind Molq will help you use it more effectively in your projects.

## Architecture Overview

Molq is built around a simple but powerful architecture:

```mermaid
graph TD
    A[Hamilton Dataflow] --> B[Molq Decorators]
    B --> C{Decorator Type}
    C -->|@cmdline| D[Command Execution]
    C -->|@submit| E[Job Submission]
    E --> F{Submitter Type}
    F -->|local| G[Local Execution]
    F -->|slurm| H[SLURM Cluster]
    D --> I[Process Result]
    G --> I
    H --> I
    I --> J[Return to Hamilton]
```

## Core Components

### 1. Decorators

Molq provides two main decorators that transform your functions into job executors:

- **`@cmdline`**: Executes shell commands within the function
- **`@submit`**: Submits jobs to registered execution backends

### 2. Submitters

Submitters are responsible for executing jobs on different platforms:

- **`LocalSubmitor`**: Runs jobs on the local machine
- **`SlurmSubmitor`**: Submits jobs to SLURM clusters
- **`BaseSubmitor`**: Base class for creating custom submitters

### 3. Generator Pattern

Molq uses Python generators to provide a clean interface for job configuration:

```python
from typing import Generator
@cmdline
def my_job():
    # The yield statement passes configuration to Molq
    result = yield {
        "cmd": "echo hello",
        "block": True
    }
    # Molq sends back the execution result
    return result.stdout.decode()
```

## Execution Flow

Here's what happens when you call a decorated function:

1. **Function Call**: You call the decorated function
2. **Generator Creation**: The decorator creates a generator from your function
3. **Configuration Yield**: Your function yields a configuration dictionary
4. **Job Execution**: Molq executes the job based on the configuration
5. **Result Return**: The execution result is sent back to your function
6. **Function Completion**: Your function processes the result and returns

## Configuration Dictionaries

Both decorators accept configuration dictionaries with specific keys:

### Common Configuration

| Key | Type | Description | Default |
|-----|------|-------------|---------|
| `cmd` | `str` or `List[str]` | Command to execute | Required |
| `cwd` | `str` or `Path` | Working directory | Current directory |
| `block` | `bool` | Wait for completion | `True` |

### Job-Specific Configuration

| Key | Type | Description | Default |
|-----|------|-------------|---------|
| `job_name` | `str` | Name of the job | Auto-generated |
| `log_file` | `str` | Path to log file | None |
| `env` | `dict` | Environment variables | None |

## Submitter Registration

The `submit` function registers submitters for later use:

```python
from typing import Generator
# Register a local submitter with name "my_local"
local = submit("my_local", "local")

# Register a SLURM submitter
cluster = submit("my_cluster", "slurm", {
    "host": "cluster.example.com",
    "username": "myuser"
})
```

The registered submitter becomes a decorator that you can use on functions.

## Blocking vs Non-Blocking Execution

### Blocking Execution (`block=True`)

```python
from typing import Generator
@cmdline
def blocking_job():
    # This will wait for the command to complete
    cp = yield {"cmd": "sleep 5", "block": True}
    return "Job completed"
```

- Function waits for job completion
- Returns the final result
- Suitable for sequential workflows

### Non-Blocking Execution (`block=False`)

```python
from typing import Generator
@local
def non_blocking_job():
    # This returns immediately with a job ID
    job_id = yield {"cmd": "sleep 60", "block": False}
    return job_id
```

- Function returns immediately
- Returns job ID or process handle
- Suitable for parallel workflows

## Error Handling

Molq handles errors at different levels:

### Command Execution Errors

```python
from typing import Generator
@cmdline
def may_fail():
    cp = yield {"cmd": "exit 1", "block": True}
    # cp.returncode will be 1
    if cp.returncode != 0:
        raise RuntimeError("Command failed")
```

### Connection Errors

For remote submitters, connection errors are propagated:

```python
from typing import Generator
try:
    result = cluster_job()
except ConnectionError:
    print("Failed to connect to cluster")
```

## Integration with Hamilton

Molq is designed to work seamlessly with Hamilton:

```python
from typing import Generator
def upstream_node() -> pd.DataFrame:
    """Regular Hamilton node."""
    return pd.DataFrame({"x": [1, 2, 3]})

@local
def process_node(upstream_node: pd.DataFrame) -> Generator[dict, int, int]:
    """Molq-decorated Hamilton node."""
    # Save input data
    upstream_node.to_csv("input.csv")
    
    # Process with external tool
    job_id = yield {
        "cmd": ["python", "process.py", "input.csv"],
        "block": True
    }
    return job_id

def downstream_node(process_node: int) -> str:
    """Regular Hamilton node that depends on Molq job."""
    return f"Processing completed with job {process_node}"
```

## Best Practices

### 1. Use Descriptive Job Names

```python
from typing import Generator
@local
def data_processing():
    job_id = yield {
        "job_name": f"process_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "cmd": ["python", "process.py"]
    }
```

### 2. Handle File Paths Carefully

```python
from typing import Generator
from pathlib import Path

@cmdline
def safe_file_operation():
    work_dir = Path("/tmp/work")
    work_dir.mkdir(exist_ok=True)
    
    cp = yield {
        "cmd": ["ls", "-la"],
        "cwd": str(work_dir),
        "block": True
    }
```

### 3. Use Environment Variables

```python
from typing import Generator
@local
def with_environment():
    job_id = yield {
        "cmd": ["python", "script.py"],
        "env": {"PYTHONPATH": "/custom/path"},
        "block": True
    }
```

## Next Steps

Now that you understand the core concepts:

- Learn about specific [Decorators](../user-guide/decorators.md) in detail
- Explore [Local Execution](../user-guide/local-execution.md) capabilities
- Set up [SLURM Integration](../user-guide/slurm-integration.md) for clusters
- Review [Configuration](../user-guide/configuration.md) options
