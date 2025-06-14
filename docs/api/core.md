# Core Functions API Reference

This section documents the core utility functions and classes that support Molq's job submission and management capabilities.

## Module Overview

The core functions provide foundational utilities for:

- Job specification validation
- Configuration management
- Error handling and logging
- Utility functions for job management

## Job Specification Validation

### `validate_job_spec(job_spec: dict, backend: str) -> dict`

Validates and normalizes a job specification dictionary.

```python
from molq.core import validate_job_spec

# Validate local job spec
local_spec = {
    'cmd': ['python', 'script.py'],
    'job_name': 'test_job'
}

validated_spec = validate_job_spec(local_spec, 'local')
print(validated_spec)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Unique name for the submitter |
| `submitter_type` | `str` | Type of submitter (`"local"`, `"slurm"`) |
| `config` | `dict` | Optional configuration for the submitter |

### Returns

Returns a decorator function that can be used to decorate functions for job submission.

### Example

```python
from molq import submit

# Local submitter
local = submit("my_local", "local")

# SLURM submitter with configuration
cluster = submit("hpc", "slurm", {
    "host": "cluster.example.com",
    "username": "user",
    "key_filename": "~/.ssh/id_rsa"
})

@local
def local_job():
    job_id = yield {"cmd": ["echo", "hello"], "block": True}
    return job_id

@cluster
def cluster_job():
    job_id = yield {
        "cmd": ["python", "script.py"],
        "partition": "compute",
        "time": "01:00:00",
        "block": False
    }
    return job_id
```

### Submitter Types

#### local

Executes jobs on the local machine.

**Configuration**: None required.

```python
local = submit("local_runner", "local")
```

#### slurm

Submits jobs to a SLURM cluster via SSH.

**Configuration options**:

| Option | Type | Description | Required |
|--------|------|-------------|----------|
| `host` | `str` | SSH hostname | ✓ |
| `username` | `str` | SSH username | ✓ |
| `port` | `int` | SSH port | ✗ (default: 22) |
| `key_filename` | `str` | SSH private key file path | ✗ |
| `password` | `str` | SSH password | ✗ |

```python
cluster = submit("my_cluster", "slurm", {
    "host": "login.cluster.edu",
    "username": "researcher",
    "key_filename": "~/.ssh/cluster_key",
    "port": 2222
})
```

### Error Handling

The `submit` function raises exceptions for invalid configurations:

```python
try:
    # Invalid submitter type
    invalid = submit("test", "invalid_type")
except ValueError as e:
    print(f"Invalid submitter type: {e}")

try:
    # Missing required configuration for SLURM
    cluster = submit("test", "slurm")  # Missing host and username
except ValueError as e:
    print(f"Missing configuration: {e}")
```

## cmdline

Pre-configured decorator for executing shell commands.

```python
@cmdline
def my_command() -> subprocess.CompletedProcess:
    result = yield {"cmd": "echo hello", "block": True}
    return result
```

The `cmdline` decorator is equivalent to:

```python
from molq import submit
local_cmdline = submit("_local_cmdline", "local")

@local_cmdline
def my_command():
    # ... same implementation
```

### Configuration

The `@cmdline` decorator accepts the same configuration options as job submitters:

| Option | Type | Description | Default | Required |
|--------|------|-------------|---------|----------|
| `cmd` | `str` or `List[str]` | Command to execute | - | ✓ |
| `cwd` | `str` or `Path` | Working directory | Current directory | ✗ |
| `block` | `bool` | Wait for completion | `True` | ✗ |
| `env` | `dict` | Environment variables | `None` | ✗ |

### Example

```python
from molq import cmdline
import subprocess

@cmdline
def list_files(directory: str = ".") -> List[str]:
    """List files in a directory."""
    cp: subprocess.CompletedProcess = yield {
        "cmd": ["ls", "-1", directory],
        "block": True
    }
    
    if cp.returncode != 0:
        raise RuntimeError(f"Failed to list files: {cp.stderr.decode()}")
    
    return cp.stdout.decode().strip().split('\n')

# Usage
files = list_files("/tmp")
print(files)
```

## Module-Level Variables

### local

Pre-configured local submitter used by the `@cmdline` decorator.

```python
from molq import local

@local
def my_local_job():
    job_id = yield {"cmd": ["echo", "using pre-configured local"], "block": True}
    return job_id
```

This is equivalent to:

```python
from molq import submit
local = submit("_local_cmdline", "local")
```

## Function Signatures

All Molq-decorated functions work with generator functions that yield configuration dictionaries:

```python
from typing import Generator, Dict, Any, Union
import subprocess

@cmdline
def example_function() -> str:
    # Type hints for the yielded value and return
    config: Dict[str, Any] = {"cmd": "echo hello", "block": True}
    result: Union[subprocess.CompletedProcess, subprocess.Popen] = yield config
    return result.stdout.decode().strip()
```

### Generator Protocol

The generator protocol used by Molq decorators:

1. **Yield**: Function yields a configuration dictionary
2. **Receive**: Function receives the execution result
3. **Return**: Function returns the final result

```python
def generator_example():
    # Step 1: Yield configuration
    result = yield {"cmd": "echo step1", "block": True}
    
    # Step 2: Process result, yield next configuration
    if result.returncode == 0:
        result2 = yield {"cmd": "echo step2", "block": True}
        return result2.stdout.decode()
    else:
        raise RuntimeError("Step 1 failed")
```

## Type Hints

Molq functions work well with Python type hints:

```python
from typing import List, Dict, Any, Union
import subprocess

@cmdline
def typed_function(input_files: List[str]) -> Dict[str, Any]:
    """Process files and return statistics."""
    results = {}
    
    for filename in input_files:
        cp: subprocess.CompletedProcess = yield {
            "cmd": ["wc", "-l", filename],
            "block": True
        }
        
        if cp.returncode == 0:
            line_count = int(cp.stdout.decode().split()[0])
            results[filename] = {"lines": line_count}
        else:
            results[filename] = {"error": cp.stderr.decode()}
    
    return results

# Type checking works correctly
file_stats: Dict[str, Any] = typed_function(["file1.txt", "file2.txt"])
```

## Configuration Validation

Molq validates configuration dictionaries and provides helpful error messages:

```python
@cmdline
def invalid_config_example():
    try:
        # Missing required 'cmd' field
        result = yield {"block": True}
    except ValueError as e:
        print(f"Configuration error: {e}")
    
    try:
        # Invalid cmd type
        result = yield {"cmd": 123, "block": True}
    except TypeError as e:
        print(f"Type error: {e}")
```

Common validation errors:

- `ValueError`: Missing required fields (`cmd`)
- `TypeError`: Invalid field types
- `FileNotFoundError`: Working directory doesn't exist
- `PermissionError`: Insufficient permissions for execution

## Async Support

Molq decorators can be used with async functions:

```python
import asyncio

@cmdline
async def async_command():
    """Async function with Molq decorator."""
    result = yield {"cmd": "echo async", "block": True}
    await asyncio.sleep(0.1)  # Some async work
    return result.stdout.decode().strip()

# Usage
async def main():
    result = await async_command()
    print(result)

asyncio.run(main())
```

## Error Propagation

Molq preserves the original function's exception behavior:

```python
@cmdline
def error_example():
    """Function that may raise various errors."""
    result = yield {"cmd": "nonexistent_command", "block": True}
    
    # This will raise subprocess.CalledProcessError if command fails
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, 
            result.args, 
            result.stdout, 
            result.stderr
        )
    
    return result.stdout.decode()

try:
    output = error_example()
except subprocess.CalledProcessError as e:
    print(f"Command failed with code {e.returncode}")
except FileNotFoundError as e:
    print(f"Command not found: {e}")
```

## Best Practices

### 1. Use Type Hints

```python
from typing import Optional
import subprocess

@cmdline
def well_typed_function(filename: str, verbose: bool = False) -> Optional[str]:
    """Process a file with proper type hints."""
    cmd = ["cat", filename]
    if verbose:
        cmd.insert(1, "-v")
    
    cp: subprocess.CompletedProcess = yield {
        "cmd": cmd,
        "block": True
    }
    
    return cp.stdout.decode() if cp.returncode == 0 else None
```

### 2. Validate Inputs

```python
import os
from pathlib import Path

@cmdline
def validated_function(input_file: str) -> str:
    """Function with input validation."""
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")
    
    if not os.access(input_file, os.R_OK):
        raise PermissionError(f"Cannot read file: {input_file}")
    
    cp = yield {
        "cmd": ["cat", input_file],
        "block": True
    }
    
    return cp.stdout.decode()
```

### 3. Handle Errors Gracefully

```python
import logging

@cmdline
def robust_function(command: str) -> Optional[str]:
    """Function with comprehensive error handling."""
    try:
        cp = yield {
            "cmd": command,
            "block": True
        }
        
        if cp.returncode != 0:
            logging.warning(f"Command failed: {cp.stderr.decode()}")
            return None
        
        return cp.stdout.decode().strip()
        
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return None
```

## Integration Examples

### With Hamilton

```python
import pandas as pd
from hamilton import driver

@cmdline
def process_csv(input_file: str) -> pd.DataFrame:
    """Process CSV file using external tool."""
    cp = yield {
        "cmd": ["python", "external_processor.py", input_file],
        "block": True
    }
    
    if cp.returncode != 0:
        raise RuntimeError(f"Processing failed: {cp.stderr.decode()}")
    
    # Assume the external tool creates output.csv
    return pd.read_csv("output.csv")

def raw_data() -> str:
    return "input.csv"

# Hamilton driver usage
config = {}
dr = driver.Driver(config, __name__)
result = dr.execute(["process_csv"], inputs={"input_file": "data.csv"})
```

### With Logging

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@cmdline
def logged_function():
    """Function with integrated logging."""
    logger.info("Starting command execution")
    
    cp = yield {
        "cmd": ["echo", "hello logging"],
        "block": True
    }
    
    if cp.returncode == 0:
        logger.info("Command completed successfully")
        return cp.stdout.decode().strip()
    else:
        logger.error(f"Command failed: {cp.stderr.decode()}")
        raise RuntimeError("Command execution failed")
```
