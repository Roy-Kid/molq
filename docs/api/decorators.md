# Decorators API Reference

This section provides comprehensive documentation for Molq's decorator functions, which are the primary interface for integrating job submission into your Python functions.

## Overview

Molq provides two main decorators:

- `@submit` - Creates custom job submitters for different execution backends
- `@cmdline` - A pre-configured decorator for local command execution

## Submit Decorator

### `submit(name: str, backend: str, config: dict = None)`

Creates a decorator that submits jobs to the specified backend.

```python
from typing import Generator
from molq import submit

# Create a decorator
local_jobs = submit('local_runner', 'local')
slurm_jobs = submit('hpc_cluster', 'slurm', {'host': 'cluster.example.com'})
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | str | Unique name for this submitter instance |
| `backend` | str | Backend type ('local' or 'slurm') |
| `config` | dict | Optional configuration for the backend |

#### Returns

Returns a decorator function that can be applied to generator functions.

#### Supported Backends

##### Local Backend

```python
from typing import Generator
local = submit('my_local', 'local', {
    'max_concurrent_jobs': 4,
    'working_directory': '/tmp/jobs',
    'environment': {'PATH': '/usr/bin:/bin'}
})
```

Configuration options for local backend:
- `max_concurrent_jobs` (int): Maximum simultaneous jobs
- `working_directory` (str): Default working directory
- `environment` (dict): Environment variables
- `shell` (str): Shell for command execution
- `job_timeout` (int): Job timeout in seconds

##### SLURM Backend

```python
from typing import Generator
slurm = submit('my_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'user',
    'partition': 'compute',
    'account': 'my_account'
})
```

Configuration options for SLURM backend:
- `host` (str): Cluster hostname (**required**)
- `username` (str): SSH username (**required**)
- `ssh_key_path` (str): SSH key path
- `partition` (str): Default partition
- `account` (str): Default account
- `timeout` (int): SSH timeout

### Using the Submit Decorator

The decorator is applied to generator functions that yield job specifications:

```python
from typing import Generator
@local_jobs
def my_job_function(param1: str, param2: int) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'script.py', param1, str(param2)],
        'job_name': f'job_{param1}_{param2}',
        'block': True
    }
    return job_id
```

#### Function Requirements

1. **Must be a generator function** - Uses `yield` to submit job
2. **Must yield a job specification dictionary**
3. **Can accept parameters** - Normal function parameters
4. **Must have return type annotation** - For Hamilton integration

#### Job Specification Format

The yielded dictionary contains job parameters:

```python
from typing import Generator
job_spec = {
    # Required
    'cmd': ['command', 'arg1', 'arg2'],  # Command to execute
    
    # Optional - Basic
    'job_name': 'my_job',                # Job name
    'block': True,                       # Wait for completion
    'working_dir': '/path/to/workdir',   # Working directory
    'environment': {'VAR': 'value'},     # Environment variables
    
    # Optional - Files
    'output_file': 'output.log',         # Stdout file
    'error_file': 'error.log',           # Stderr file
    
    # SLURM-specific (when using SLURM backend)
    'cpus_per_task': 4,                  # CPU cores
    'memory': '16G',                     # Memory requirement
    'time': '02:00:00',                  # Time limit
    'partition': 'compute',              # Queue/partition
    'gres': 'gpu:2',                     # GPU resources
    'dependency': 'afterok:12345',       # Job dependencies
    'array': '1-10',                     # Job array specification
}
```

## Command Line Decorator

### `@cmdline`

A pre-configured decorator for local command execution.

```python
from typing import Generator
from molq import cmdline

@cmdline
def run_command() -> str:
    process = yield {'cmd': 'echo hello', 'block': True}
    return process.stdout.decode().strip()
```

The `@cmdline` decorator is equivalent to:

```python
from typing import Generator
local = submit('_local_cmdline', 'local')

@local
def run_command() -> str:
    job_id = yield {'cmd': 'echo hello', 'block': True}
    # Returns subprocess.CompletedProcess when block=True
    return job_id
```

#### Differences from @submit

1. **Always local execution** - No configuration needed
2. **Returns process object** - When `block=True`, returns `subprocess.CompletedProcess`
3. **Simplified for shell commands** - Optimized for command-line operations

#### Example Usage

```python
from typing import Generator
from molq import cmdline

@cmdline
def get_system_info() -> dict:
    # Get CPU info
    cpu_process = yield {'cmd': 'nproc', 'block': True}
    cpu_count = int(cpu_process.stdout.decode().strip())
    
    # Get memory info
    mem_process = yield {'cmd': 'free -m', 'block': True}
    mem_output = mem_process.stdout.decode()
    
    return {
        'cpu_count': cpu_count,
        'memory_info': mem_output
    }

# Use the function
system_info = get_system_info()
print(f"CPUs: {system_info['cpu_count']}")
```

## Advanced Usage Patterns

### Multiple Backends

You can create multiple decorators for different execution environments:

```python
from typing import Generator
from molq import submit

# Local development
dev_local = submit('dev', 'local', {
    'working_directory': '/tmp/dev_jobs'
})

# Production cluster
prod_cluster = submit('prod', 'slurm', {
    'host': 'prod-cluster.com',
    'username': 'prod_user',
    'partition': 'production'
})

# Testing cluster
test_cluster = submit('test', 'slurm', {
    'host': 'test-cluster.com',
    'username': 'test_user',
    'partition': 'testing'
})

# Use different decorators for different purposes
@dev_local
def develop_algorithm() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'develop.py'],
        'job_name': 'development',
        'block': True
    }
    return job_id

@test_cluster
def test_algorithm() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'test.py'],
        'job_name': 'testing',
        'cpus_per_task': 2,
        'memory': '8G',
        'time': '01:00:00',
        'block': False
    }
    return job_id

@prod_cluster
def run_production() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'production.py'],
        'job_name': 'production_run',
        'cpus_per_task': 16,
        'memory': '64G',
        'time': '12:00:00',
        'block': False
    }
    return job_id
```

### Parameter-Driven Backend Selection

```python
from typing import Generator
import os
from molq import submit

def get_submitter(environment='local'):
    """Factory function to get appropriate submitter"""
    if environment == 'local':
        return submit('local_env', 'local')
    elif environment == 'cluster':
        return submit('cluster_env', 'slurm', {
            'host': 'cluster.example.com',
            'username': os.environ['USER']
        })
    else:
        raise ValueError(f"Unknown environment: {environment}")

# Use environment variable or parameter
env = os.environ.get('COMPUTE_ENV', 'local')
compute = get_submitter(env)

@compute
def adaptive_job() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'analysis.py'],
        'job_name': 'adaptive_job',
        'block': False
    }
    return job_id
```

### Job Chaining and Dependencies

```python
from typing import Generator
from molq import submit

slurm = submit('cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'user'
})

@slurm
def preprocess_data() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'preprocess.py'],
        'job_name': 'preprocess',
        'cpus_per_task': 4,
        'memory': '16G',
        'time': '01:00:00',
        'block': False
    }
    return job_id

@slurm
def analyze_data(prep_job_id: int) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'analyze.py'],
        'job_name': 'analysis',
        'dependency': f'afterok:{prep_job_id}',
        'cpus_per_task': 8,
        'memory': '32G',
        'time': '04:00:00',
        'block': False
    }
    return job_id

# Chain jobs
prep_job = preprocess_data()
analysis_job = analyze_data(prep_job)
print(f"Analysis job {analysis_job} depends on preprocessing job {prep_job}")
```

### Job Arrays with Decorators

```python
from typing import Generator
@slurm
def parameter_sweep(start: int, end: int, max_concurrent: int = 5) -> Generator[dict, int, int]:
    array_spec = f"{start}-{end}%{max_concurrent}"
    
    job_id = yield {
        'cmd': ['python', 'sweep.py', '$SLURM_ARRAY_TASK_ID'],
        'job_name': 'param_sweep',
        'array': array_spec,
        'cpus_per_task': 2,
        'memory': '4G',
        'time': '00:30:00',
        'output_file': 'sweep_%A_%a.out',
        'error_file': 'sweep_%A_%a.err',
        'block': False
    }
    return job_id

# Submit parameter sweep
sweep_job = parameter_sweep(1, 100, 10)  # 100 jobs, max 10 concurrent
```

## Integration with Hamilton

### Basic Integration

```python
from typing import Generator
import hamilton.driver
from molq import submit

# Create submitter
cluster = submit('compute_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'researcher'
})

# Hamilton functions with job submission
@cluster
def data_processing(input_file: str) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'process.py', input_file],
        'job_name': 'data_processing',
        'cpus_per_task': 4,
        'memory': '16G',
        'time': '02:00:00',
        'block': False
    }
    return job_id

@cluster
def model_training(processing_job_id: int) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'train.py'],
        'job_name': 'model_training',
        'dependency': f'afterok:{processing_job_id}',
        'gres': 'gpu:2',
        'cpus_per_task': 8,
        'memory': '32G',
        'time': '12:00:00',
        'block': False
    }
    return job_id

# Create Hamilton driver and execute
dr = hamilton.driver.Driver({}, data_processing, model_training)
results = dr.execute(['model_training'], inputs={'input_file': 'data.csv'})
```

### Mixed Local and Remote Execution

```python
from typing import Generator
import hamilton.driver
from molq import submit, cmdline

# Different backends for different tasks
local = submit('local_tasks', 'local')
cluster = submit('cluster_tasks', 'slurm', {'host': 'cluster.example.com'})

# Local preprocessing
@cmdline
def download_data(url: str) -> str:
    process = yield {
        'cmd': ['curl', '-o', 'data.zip', url],
        'block': True
    }
    return 'data.zip'

@cmdline
def extract_data(zip_file: str) -> str:
    process = yield {
        'cmd': ['unzip', zip_file, '-d', 'extracted/'],
        'block': True
    }
    return 'extracted/'

# Remote compute-intensive tasks
@cluster
def heavy_computation(data_dir: str) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'compute.py', data_dir],
        'job_name': 'heavy_compute',
        'cpus_per_task': 32,
        'memory': '128G',
        'time': '24:00:00',
        'block': False
    }
    return job_id

# Local post-processing
@cmdline
def generate_report(job_id: int) -> str:
    # Wait for cluster job to complete (simplified)
    process = yield {
        'cmd': ['python', 'generate_report.py', str(job_id)],
        'block': True
    }
    return 'report.html'

# Execute mixed workflow
dr = hamilton.driver.Driver(
    {}, 
    download_data, 
    extract_data, 
    heavy_computation, 
    generate_report
)

results = dr.execute(
    ['generate_report'], 
    inputs={'url': 'https://example.com/data.zip'}
)
```

## Error Handling

### Decorator-Level Error Handling

```python
from typing import Generator
from molq import submit
from molq.exceptions import SubmissionError, JobExecutionError

cluster = submit('error_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'user'
})

@cluster
def robust_job(input_file: str) -> Generator[dict, int, int]:
    try:
        job_id = yield {
            'cmd': ['python', 'process.py', input_file],
            'job_name': 'robust_processing',
            'cpus_per_task': 4,
            'memory': '16G',
            'time': '02:00:00',
            'block': False
        }
        return job_id
        
    except SubmissionError as e:
        print(f"Failed to submit job: {e}")
        # Could implement retry logic here
        raise
        
    except JobExecutionError as e:
        print(f"Job execution failed: {e}")
        raise

# Usage with error handling
try:
    job_id = robust_job('input.txt')
    print(f"Job submitted successfully: {job_id}")
except Exception as e:
    print(f"Job failed: {e}")
```

### Retry Logic with Decorators

```python
from typing import Generator
from functools import wraps
import time

def retry_on_failure(max_retries=3, delay=60):
    """Decorator to add retry logic to job submission"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        print(f"Attempt {attempt + 1} failed: {e}")
                        print(f"Retrying in {delay} seconds...")
                        time.sleep(delay)
                    else:
                        print(f"All {max_retries} attempts failed")
            
            raise last_exception
        return wrapper
    return decorator

# Apply retry logic to job functions
@retry_on_failure(max_retries=3, delay=30)
@cluster
def unreliable_job() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'unreliable_script.py'],
        'job_name': 'unreliable_job',
        'block': False
    }
    return job_id
```

## Performance Considerations

### Avoiding Decorator Overhead

```python
from typing import Generator
# Create submitters once, reuse multiple times
local_submitter = submit('shared_local', 'local')
cluster_submitter = submit('shared_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'user'
})

# Use the same submitter for multiple functions
@local_submitter
def job_1() -> Generator[dict, int, int]:
    job_id = yield {'cmd': ['task1'], 'block': False}
    return job_id

@local_submitter
def job_2() -> Generator[dict, int, int]:
    job_id = yield {'cmd': ['task2'], 'block': False}
    return job_id

@cluster_submitter
def cluster_job_1() -> Generator[dict, int, int]:
    job_id = yield {'cmd': ['cluster_task1'], 'block': False}
    return job_id
```

### Connection Pooling

```python
from typing import Generator
# Configure connection pooling for SLURM submitters
cluster = submit('pooled_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'user',
    'connection_pool_size': 5,  # Maintain 5 connections
    'keep_alive_interval': 60   # Keep connections alive
})
```

## Best Practices

### 1. Naming Conventions

```python
from typing import Generator
# Use descriptive names for submitters
local_dev = submit('local_development', 'local')
hpc_production = submit('hpc_production', 'slurm', config)
gpu_cluster = submit('gpu_training', 'slurm', gpu_config)

# Use descriptive job names
@hpc_production
def ml_model_training(dataset: str, model_type: str) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'train.py', dataset, model_type],
        'job_name': f'train_{model_type}_{dataset}',
        # ... other parameters
    }
    return job_id
```

### 2. Configuration Management

```python
from typing import Generator
import os
from molq import submit

def create_cluster_submitter():
    """Factory function with environment-based configuration"""
    config = {
        'host': os.environ.get('CLUSTER_HOST', 'default-cluster.com'),
        'username': os.environ.get('CLUSTER_USER', os.environ['USER']),
        'partition': os.environ.get('CLUSTER_PARTITION', 'compute'),
        'account': os.environ.get('CLUSTER_ACCOUNT')
    }
    
    # Remove None values
    config = {k: v for k, v in config.items() if v is not None}
    
    return submit('env_cluster', 'slurm', config)

cluster = create_cluster_submitter()
```

### 3. Resource Right-Sizing

```python
from typing import Generator
# Define resource profiles
RESOURCE_PROFILES = {
    'small': {'cpus_per_task': 1, 'memory': '4G', 'time': '01:00:00'},
    'medium': {'cpus_per_task': 4, 'memory': '16G', 'time': '04:00:00'},
    'large': {'cpus_per_task': 16, 'memory': '64G', 'time': '12:00:00'},
    'gpu': {'cpus_per_task': 8, 'memory': '32G', 'time': '08:00:00', 'gres': 'gpu:2'}
}

@cluster
def scalable_job(task: str, profile: str = 'medium') -> Generator[dict, int, int]:
    resources = RESOURCE_PROFILES[profile]
    
    job_spec = {
        'cmd': ['python', 'task.py', task],
        'job_name': f'{task}_{profile}',
        **resources,
        'block': False
    }
    
    job_id = yield job_spec
    return job_id
```

### 4. Testing and Development

```python
from typing import Generator
import os
from molq import submit

# Use different submitters based on environment
if os.environ.get('DEVELOPMENT_MODE'):
    # Use local execution for development
    compute = submit('dev_local', 'local', {'max_concurrent_jobs': 2})
else:
    # Use cluster for production
    compute = submit('prod_cluster', 'slurm', {
        'host': 'prod-cluster.com',
        'username': 'prod_user'
    })

@compute
def environment_aware_job() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'job.py'],
        'job_name': 'env_aware_job',
        'block': True  # Block in development for easier debugging
    }
    return job_id
```

## Next Steps

- Learn about [Submitters API](submitters.md) for lower-level control
- Explore [Core Functions](core.md) for utility functions
- Check [Examples](../examples/local-jobs.md) for practical usage patterns
- Review [Configuration Guide](../user-guide/configuration.md) for advanced setups
