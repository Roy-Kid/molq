# Local Execution

The local execution backend allows you to run jobs on your local machine using Molq's job management interface. This is useful for development, testing, and single-machine workflows.

## LocalSubmitor

The `LocalSubmitor` class handles job execution on the local machine. It's automatically used when you create a submitter with type `"local"`.

### Basic Setup

```python
from molq import submit

# Create a local submitter
local = submit("my_local", "local")

@local
def local_job():
    job_id = yield {
        "job_name": "local_test",
        "cmd": ["echo", "Hello Local!"],
        "block": True
    }
    return job_id
```

## Configuration Options

### Standard Options

All standard job configuration options are supported:

```python
@local
def configured_job():
    job_id = yield {
        "job_name": "data_processing",
        "cmd": ["python", "process_data.py"],
        "cwd": "/path/to/work/directory",
        "block": True,
        "log_file": "processing.log",
        "env": {
            "PYTHONPATH": "/custom/python/path",
            "DATA_DIR": "/data/input"
        }
    }
    return job_id
```

### Environment Variables

Set custom environment variables for your jobs:

```python
@local
def job_with_env():
    job_id = yield {
        "cmd": ["python", "-c", "import os; print(os.getenv('CUSTOM_VAR'))"],
        "env": {
            "CUSTOM_VAR": "Hello from environment!",
            "PATH": f"/custom/bin:{os.environ['PATH']}"
        },
        "block": True
    }
    return job_id
```

### Working Directory

Control where your job runs:

```python
import tempfile
from pathlib import Path

@local
def job_with_workdir():
    # Create a temporary working directory
    with tempfile.TemporaryDirectory() as tmpdir:
        work_path = Path(tmpdir)
        
        # Create some test files
        (work_path / "input.txt").write_text("Hello World")
        
        job_id = yield {
            "cmd": ["cat", "input.txt"],
            "cwd": str(work_path),
            "block": True
        }
    return job_id
```

## Blocking vs Non-Blocking Execution

### Blocking Execution

Wait for job completion and get the full result:

```python
@local
def blocking_job():
    job_id = yield {
        "cmd": ["python", "-c", "import time; time.sleep(2); print('Done')"],
        "block": True
    }
    print(f"Job {job_id} completed")
    return job_id
```

### Non-Blocking Execution

Start a job and continue immediately:

```python
import time

@local
def non_blocking_job():
    # Start a long-running job
    job_id = yield {
        "cmd": ["python", "-c", "import time; time.sleep(10); print('Long job done')"],
        "block": False
    }
    
    print(f"Started job {job_id}, continuing with other work...")
    
    # Do other work while job runs
    time.sleep(1)
    
    return job_id
```

## Process Management

### Process Information

When using non-blocking execution, you get access to process information:

```python
@local
def process_info_job():
    job_id = yield {
        "cmd": ["python", "-c", "import time; time.sleep(5)"],
        "block": False
    }
    
    # job_id is actually the process object for local execution
    print(f"Process PID: {job_id.pid}")
    print(f"Process poll result: {job_id.poll()}")  # None if still running
    
    return job_id
```

### Process Monitoring

Monitor running processes:

```python
import time
import psutil

@local
def monitored_job():
    job_id = yield {
        "cmd": ["python", "-c", "import time; [time.sleep(1) for _ in range(10)]"],
        "block": False
    }
    
    # Monitor the process
    process = psutil.Process(job_id.pid)
    
    while process.is_running():
        print(f"Process status: {process.status()}")
        print(f"CPU percent: {process.cpu_percent()}")
        print(f"Memory info: {process.memory_info()}")
        time.sleep(1)
    
    return job_id
```

## File Operations

### Input/Output Files

Handle file input/output in local jobs:

```python
import tempfile
import json

@local
def file_processing_job():
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = f"{tmpdir}/input.json"
        output_file = f"{tmpdir}/output.json"
        
        # Prepare input data
        data = {"numbers": [1, 2, 3, 4, 5]}
        with open(input_file, 'w') as f:
            json.dump(data, f)
        
        # Process the file
        job_id = yield {
            "cmd": [
                "python", "-c",
                f"""
import json
with open('{input_file}') as f:
    data = json.load(f)
result = {{'sum': sum(data['numbers'])}}
with open('{output_file}', 'w') as f:
    json.dump(result, f)
"""
            ],
            "block": True
        }
        
        # Read the result
        with open(output_file) as f:
            result = json.load(f)
        
        return result
```

### Log Files

Capture job output to log files:

```python
@local
def logged_job():
    log_path = "/tmp/job_output.log"
    
    job_id = yield {
        "cmd": ["python", "-c", "print('This will be logged'); print('Error message', file=sys.stderr)"],
        "log_file": log_path,
        "block": True
    }
    
    # Read the log file
    with open(log_path) as f:
        log_content = f.read()
    
    print(f"Job {job_id} log content:\n{log_content}")
    return job_id
```

## Error Handling

### Command Errors

Handle command execution errors:

```python
@local
def error_handling_job():
    try:
        job_id = yield {
            "cmd": ["python", "-c", "raise ValueError('Intentional error')"],
            "block": True
        }
        return job_id
    except subprocess.CalledProcessError as e:
        print(f"Command failed with return code {e.returncode}")
        print(f"Error output: {e.stderr}")
        return None
```

### Resource Errors

Handle resource-related errors:

```python
import shutil
import os

@local
def resource_check_job():
    # Check available disk space
    free_space = shutil.disk_usage("/tmp").free
    required_space = 1024 * 1024 * 100  # 100MB
    
    if free_space < required_space:
        raise RuntimeError("Insufficient disk space")
    
    # Check if required executables exist
    if not shutil.which("python"):
        raise RuntimeError("Python executable not found")
    
    job_id = yield {
        "cmd": ["python", "-c", "print('Resource checks passed')"],
        "block": True
    }
    return job_id
```

## Advanced Patterns

### Job Chains

Chain multiple jobs together:

```python
@local
def job_chain():
    # Job 1: Data preparation
    job1_id = yield {
        "job_name": "prepare_data",
        "cmd": ["python", "-c", "with open('/tmp/data.txt', 'w') as f: f.write('prepared data')"],
        "block": True
    }
    
    # Job 2: Data processing
    job2_id = yield {
        "job_name": "process_data",
        "cmd": ["python", "-c", "with open('/tmp/data.txt') as f: print(f'Processing: {f.read()}')"],
        "block": True
    }
    
    # Job 3: Cleanup
    job3_id = yield {
        "job_name": "cleanup",
        "cmd": ["rm", "/tmp/data.txt"],
        "block": True
    }
    
    return [job1_id, job2_id, job3_id]
```

### Parallel Jobs

Submit multiple jobs in parallel:

```python
@local
def parallel_jobs():
    job_configs = [
        {
            "job_name": f"parallel_job_{i}",
            "cmd": ["python", "-c", f"import time; time.sleep({i}); print('Job {i} done')"],
            "block": False
        }
        for i in range(1, 4)
    ]
    
    job_ids = []
    for config in job_configs:
        job_id = yield config
        job_ids.append(job_id)
    
    # Wait for all jobs to complete
    for job_id in job_ids:
        job_id.wait()
    
    return job_ids
```

### Conditional Execution

Execute jobs based on conditions:

```python
import os

@local
def conditional_job():
    # Check if input file exists
    input_file = "/tmp/input_data.txt"
    
    if os.path.exists(input_file):
        job_id = yield {
            "cmd": ["python", "process_existing_file.py", input_file],
            "block": True
        }
    else:
        job_id = yield {
            "cmd": ["python", "generate_default_data.py"],
            "block": True
        }
    
    return job_id
```

## Performance Considerations

### Resource Monitoring

Monitor resource usage during job execution:

```python
import psutil
import threading
import time

def monitor_resources(pid, duration=60):
    """Monitor process resources for a given duration."""
    process = psutil.Process(pid)
    start_time = time.time()
    
    max_memory = 0
    total_cpu = 0
    samples = 0
    
    while time.time() - start_time < duration and process.is_running():
        try:
            memory = process.memory_info().rss / 1024 / 1024  # MB
            cpu = process.cpu_percent()
            
            max_memory = max(max_memory, memory)
            total_cpu += cpu
            samples += 1
            
            time.sleep(1)
        except psutil.NoSuchProcess:
            break
    
    avg_cpu = total_cpu / samples if samples > 0 else 0
    return {"max_memory_mb": max_memory, "avg_cpu_percent": avg_cpu}

@local
def monitored_resource_job():
    job_id = yield {
        "cmd": ["python", "-c", "import time; [time.sleep(0.1) for _ in range(100)]"],
        "block": False
    }
    
    # Start monitoring in a separate thread
    monitor_thread = threading.Thread(
        target=lambda: print(f"Resource usage: {monitor_resources(job_id.pid, 15)}")
    )
    monitor_thread.start()
    
    # Wait for job completion
    job_id.wait()
    monitor_thread.join()
    
    return job_id
```

### Memory Management

Handle memory-intensive jobs:

```python
@local
def memory_intensive_job():
    # Check available memory before starting
    available_memory = psutil.virtual_memory().available / 1024 / 1024  # MB
    required_memory = 1024  # MB
    
    if available_memory < required_memory:
        raise RuntimeError(f"Insufficient memory: {available_memory}MB available, {required_memory}MB required")
    
    job_id = yield {
        "cmd": [
            "python", "-c",
            "import numpy as np; arr = np.random.random((10000, 10000)); print(f'Array shape: {arr.shape}')"
        ],
        "block": True
    }
    return job_id
```

## Best Practices for Local Execution

### 1. Use Temporary Directories

```python
import tempfile
from pathlib import Path

@local
def clean_job():
    with tempfile.TemporaryDirectory() as tmpdir:
        work_dir = Path(tmpdir)
        
        job_id = yield {
            "cmd": ["python", "my_script.py"],
            "cwd": str(work_dir),
            "block": True
        }
    # Temporary directory is automatically cleaned up
    return job_id
```

### 2. Validate Dependencies

```python
import shutil

@local
def validated_job():
    # Check for required executables
    required_tools = ["python", "pip", "git"]
    for tool in required_tools:
        if not shutil.which(tool):
            raise RuntimeError(f"Required tool '{tool}' not found in PATH")
    
    job_id = yield {
        "cmd": ["python", "my_script.py"],
        "block": True
    }
    return job_id
```

### 3. Set Timeouts

```python
import signal
import threading

@local
def timeout_job():
    def timeout_handler():
        time.sleep(30)  # 30 second timeout
        print("Job timed out!")
        # Handle timeout (could terminate process)
    
    timeout_thread = threading.Thread(target=timeout_handler, daemon=True)
    timeout_thread.start()
    
    job_id = yield {
        "cmd": ["python", "potentially_long_script.py"],
        "block": True
    }
    return job_id
```

## Troubleshooting

### Common Issues

1. **Permission Errors**: Ensure the user has execute permissions on commands and write permissions on working directories.

2. **Path Issues**: Use absolute paths or ensure relative paths are correct from the working directory.

3. **Environment Variables**: Remember that jobs run in a separate process with potentially different environment variables.

4. **Resource Limits**: Be aware of system resource limits (memory, file descriptors, etc.).

### Debugging Tips

```python
import logging

logging.basicConfig(level=logging.DEBUG)

@local
def debug_job():
    logging.info("Starting debug job")
    
    job_id = yield {
        "cmd": ["python", "-c", "import sys; print(f'Python: {sys.executable}'); print(f'Path: {sys.path}')"],
        "block": True,
        "log_file": "/tmp/debug.log"
    }
    
    logging.info(f"Job {job_id} completed")
    return job_id
```

## Next Steps

- Learn about [SLURM Integration](slurm-integration.md) for cluster computing
- Explore [Configuration](configuration.md) options for advanced setups
- Check out [Examples](../examples/local-jobs.md) for real-world local job patterns
- See [API Reference](../api/submitters.md) for detailed class documentation
