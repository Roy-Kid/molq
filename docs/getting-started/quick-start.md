# Quick Start

This guide will help you get started with Molq in just a few minutes.

## Basic Usage

Molq provides two main decorators for job execution:

### 1. Command Line Execution

The `@cmdline` decorator runs shell commands within your functions:

```python title="simple_cmdline.py"
from molq import cmdline

@cmdline
def echo_hello() -> str:
    cp = yield {"cmd": "echo 'Hello, Molq!'", "block": True}
    return cp.stdout.decode().strip()

if __name__ == "__main__":
    result = echo_hello()
    print(result)  # Output: Hello, Molq!
```

### 2. Job Submission

The `@submit` decorator registers job runners and submits jobs to them:

```python title="local_job.py"
from molq import submit
from typing import Generator

# Register a local submitter
local = submit('local', 'local')

@local
def sleep_job() -> Generator[dict, int, int]:
    job_id = yield {
        'job_name': 'my_sleep_job',
        'cmd': ['sleep', '2'],
        'block': True,
    }
    return job_id

if __name__ == "__main__":
    job_id = sleep_job()
    print(f"Job completed with ID: {job_id}")
```

## Configuration Options

Both decorators accept configuration dictionaries with various options:

### Command Line Options

```python
@cmdline
def advanced_command() -> str:
    cp = yield {
        "cmd": ["python", "--version"],  # Command as list or string
        "cwd": "/tmp",                   # Working directory
        "block": True,                   # Wait for completion
    }
    return cp.stdout.decode().strip()
```

### Job Submission Options

```python
@local
def advanced_job() -> int:
    job_id = yield {
        "job_name": "data_processing",   # Job name
        "cmd": ["python", "process.py"], # Command to run
        "cwd": "/data",                  # Working directory
        "block": True,                   # Wait for completion
        "log_file": "job.log",          # Log file path
    }
    return job_id
```

## Working with Hamilton

Molq is designed to work seamlessly with Hamilton dataflows:

```python title="hamilton_example.py"
import pandas as pd
from hamilton import driver
from molq import submit, cmdline

# Hamilton configuration
config = {}
dr = driver.Driver(config, __name__)

local = submit('local', 'local')

def raw_data() -> pd.DataFrame:
    """Load raw data."""
    return pd.DataFrame({'x': [1, 2, 3], 'y': [4, 5, 6]})

@local
def process_data(raw_data: pd.DataFrame) -> int:
    """Process data using external tool."""
    # Save data for processing
    raw_data.to_csv('/tmp/input.csv', index=False)
    
    # Submit processing job
    job_id = yield {
        'job_name': 'data_processing',
        'cmd': ['python', 'external_processor.py', '/tmp/input.csv'],
        'block': True,
    }
    return job_id

@cmdline
def collect_results(process_data: int) -> str:
    """Collect processing results."""
    cp = yield {
        'cmd': 'cat /tmp/output.csv',
        'block': True
    }
    return cp.stdout.decode().strip()

if __name__ == "__main__":
    result = dr.execute(['collect_results'])
    print(result)
```

## Error Handling

Handle errors gracefully in your jobs:

```python
@cmdline
def safe_command() -> str:
    try:
        cp = yield {"cmd": "nonexistent_command", "block": True}
        return cp.stdout.decode().strip()
    except Exception as e:
        return f"Command failed: {e}"
```

## Non-blocking Execution

For long-running jobs, use non-blocking execution:

```python
@local
def long_running_job() -> int:
    # Start job without waiting
    job_id = yield {
        'job_name': 'long_task',
        'cmd': ['sleep', '60'],
        'block': False,  # Don't wait for completion
    }
    return job_id
```

## Next Steps

Now that you understand the basics:

- Learn about [Basic Concepts](concepts.md) for deeper understanding
- Explore [Local Execution](../user-guide/local-execution.md) for detailed local job configuration
- Check out [SLURM Integration](../user-guide/slurm-integration.md) for cluster computing
- Browse [Examples](../examples/cmdline.md) for real-world use cases
