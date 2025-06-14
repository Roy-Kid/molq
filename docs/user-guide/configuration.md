# Configuration

Molq provides flexible configuration options for different execution environments and job schedulers. This guide covers all available configuration parameters and best practices.

## Configuration Hierarchy

Molq uses a hierarchical configuration system:

1. **Default values** - Built-in defaults for all parameters
2. **Global configuration** - System-wide settings
3. **Submitter configuration** - Per-submitter settings  
4. **Job-level parameters** - Individual job overrides

## Submitter Configuration

### Local Submitter

```python title="local_config.py"
from typing import Generator
from molq import submit

# Basic local configuration
local = submit('local_runner', 'local')

# Advanced local configuration
local_advanced = submit('local_advanced', 'local', {
    'max_concurrent_jobs': 4,
    'job_timeout': 3600,  # seconds
    'working_directory': '/tmp/molq_jobs',
    'shell': '/bin/bash',
    'environment': {
        'PATH': '/usr/local/bin:/usr/bin:/bin',
        'PYTHONPATH': '/path/to/modules'
    }
})
```

#### Local Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_concurrent_jobs` | int | `None` | Maximum simultaneous jobs |
| `job_timeout` | int | `None` | Job timeout in seconds |
| `working_directory` | str | current dir | Job working directory |
| `shell` | str | `'/bin/sh'` | Shell for command execution |
| `environment` | dict | `{}` | Environment variables |

### SLURM Submitter

```python title="slurm_config.py"
from typing import Generator
from molq import submit

# Basic SLURM configuration
slurm = submit('hpc_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'your_username',
    'ssh_key_path': '~/.ssh/id_rsa'
})

# Advanced SLURM configuration
slurm_advanced = submit('hpc_advanced', 'slurm', {
    # Connection settings
    'host': 'cluster.example.com',
    'port': 22,
    'username': 'user',
    'password': None,  # Use key-based auth
    'ssh_key_path': '~/.ssh/cluster_key',
    'ssh_key_passphrase': None,
    'timeout': 30,
    
    # SLURM defaults
    'partition': 'compute',
    'account': 'project123',
    'qos': 'normal',
    'mail_type': 'FAIL',
    'mail_user': 'user@example.com',
    
    # Resource defaults
    'cpus_per_task': 1,
    'memory': '1G',
    'time': '01:00:00',
    'nodes': 1,
    
    # File management
    'work_dir': '/scratch/$USER',
    'output_dir': '/scratch/$USER/logs',
    'output_pattern': '%x_%j.out',
    'error_pattern': '%x_%j.err',
    
    # Behavior
    'max_concurrent_jobs': 100,
    'job_check_interval': 30,
    'retry_attempts': 3
})
```

#### SLURM Configuration Parameters

##### Connection Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | str | **required** | Cluster hostname |
| `port` | int | `22` | SSH port |
| `username` | str | **required** | SSH username |
| `password` | str | `None` | SSH password (not recommended) |
| `ssh_key_path` | str | `~/.ssh/id_rsa` | SSH private key path |
| `ssh_key_passphrase` | str | `None` | SSH key passphrase |
| `timeout` | int | `30` | SSH connection timeout |

##### SLURM Defaults

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `partition` | str | `None` | Default partition |
| `account` | str | `None` | Default account |
| `qos` | str | `None` | Quality of service |
| `mail_type` | str | `None` | Email notification types |
| `mail_user` | str | `None` | Email address |

##### Resource Defaults

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cpus_per_task` | int | `1` | Default CPU cores |
| `memory` | str | `1G` | Default memory |
| `time` | str | `01:00:00` | Default time limit |
| `nodes` | int | `1` | Default node count |

## Job-Level Configuration

Individual jobs can override submitter defaults:

```python title="job_config.py"
from typing import Generator
from molq import submit

slurm = submit('cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'user',
    # Default resources
    'cpus_per_task': 1,
    'memory': '2G',
    'time': '01:00:00'
})

@slurm
def small_job() -> Generator[dict, int, int]:
    # Uses default resources
    job_id = yield {
        'cmd': ['python', 'small_script.py'],
        'job_name': 'small_job'
    }
    return job_id

@slurm
def large_job() -> Generator[dict, int, int]:
    # Override default resources
    job_id = yield {
        'cmd': ['python', 'large_script.py'],
        'job_name': 'large_job',
        'cpus_per_task': 16,
        'memory': '64G',
        'time': '12:00:00',
        'partition': 'highmem'
    }
    return job_id
```

## Environment Configuration

### Environment Variables

```python title="environment.py"
from typing import Generator
# Global environment for all jobs
local_with_env = submit('local_env', 'local', {
    'environment': {
        'PYTHONPATH': '/path/to/modules',
        'OMP_NUM_THREADS': '4',
        'CUDA_VISIBLE_DEVICES': '0,1'
    }
})

@local_with_env
def job_with_env() -> Generator[dict, int, int]:
    # Additional environment for this job
    job_id = yield {
        'cmd': ['python', 'script.py'],
        'environment': {
            'JOB_ID': '12345',
            'DEBUG': 'true'
        }
    }
    return job_id
```

### Module Loading (SLURM)

```python title="modules.py"
from typing import Generator
slurm = submit('cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'user'
})

@slurm
def job_with_modules() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': [
            'module load python/3.9 gcc/9.3.0',
            'python script.py'
        ],
        'job_name': 'module_job',
        'shell': '/bin/bash'
    }
    return job_id
```

## File Management Configuration

### Working Directories

```python title="directories.py"
from typing import Generator
# Configure working directories
slurm = submit('cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'user',
    'work_dir': '/scratch/$USER',
    'output_dir': '/scratch/$USER/logs'
})

@slurm
def job_with_dirs() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'process.py'],
        'job_name': 'processing',
        'work_dir': '/scratch/$USER/job_$SLURM_JOB_ID',
        'output_file': '/scratch/$USER/logs/job_%j.out',
        'error_file': '/scratch/$USER/logs/job_%j.err'
    }
    return job_id
```

### File Transfer

```python title="file_transfer.py"
from typing import Generator
# Automatic file staging
@slurm
def job_with_staging() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'analyze.py', 'input.dat'],
        'job_name': 'analysis',
        'input_files': [
            'local_input.dat',
            'scripts/analyze.py'
        ],
        'output_files': [
            'results.txt',
            'plots/*.png'
        ],
        'stage_in_dir': '/scratch/$USER/staging',
        'stage_out_dir': './results'
    }
    return job_id
```

## Logging Configuration

### Enable Debug Logging

```python title="logging_config.py"
from typing import Generator
import logging

# Enable debug logging for Molq
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Configure specific loggers
molq_logger = logging.getLogger('molq')
molq_logger.setLevel(logging.INFO)

# Add file handler
handler = logging.FileHandler('molq.log')
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
molq_logger.addHandler(handler)
```

### Job-Specific Logging

```python title="job_logging.py"
from typing import Generator
@slurm
def logged_job() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'script.py'],
        'job_name': 'logged_job',
        'output_file': f'logs/job_{job_id}.out',
        'error_file': f'logs/job_{job_id}.err',
        'verbose': True  # Enable verbose SLURM output
    }
    return job_id
```

## Configuration Files

### YAML Configuration

```yaml title="molq_config.yaml"
# Default submitter configurations
submitters:
  local:
    type: local
    max_concurrent_jobs: 4
    working_directory: /tmp/molq
    environment:
      PYTHONPATH: /path/to/modules
  
  hpc:
    type: slurm
    host: cluster.example.com
    username: user
    ssh_key_path: ~/.ssh/cluster_key
    partition: compute
    account: project123
    defaults:
      cpus_per_task: 1
      memory: 2G
      time: "01:00:00"

# Global settings
global:
  log_level: INFO
  log_file: molq.log
  max_retries: 3
```

### Loading Configuration

```python title="load_config.py"
from typing import Generator
import yaml
from molq import submit

# Load configuration from file
with open('molq_config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Create submitters from config
local = submit('local', 'local', config['submitters']['local'])
hpc = submit('hpc', 'slurm', config['submitters']['hpc'])
```

## Security Configuration

### SSH Key Management

```python title="security.py"
from typing import Generator
# Use different SSH keys for different clusters
production_cluster = submit('prod', 'slurm', {
    'host': 'prod-cluster.example.com',
    'username': 'prod_user',
    'ssh_key_path': '~/.ssh/prod_cluster_key',
    'ssh_key_passphrase': 'secure_passphrase'
})

development_cluster = submit('dev', 'slurm', {
    'host': 'dev-cluster.example.com', 
    'username': 'dev_user',
    'ssh_key_path': '~/.ssh/dev_cluster_key'
})
```

### SSH Agent Configuration

```bash
# Use SSH agent for key management
eval $(ssh-agent -s)
ssh-add ~/.ssh/cluster_key
```

```python title="ssh_agent.py"
from typing import Generator
# Molq will use SSH agent automatically
cluster = submit('cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'user'
    # No ssh_key_path needed when using SSH agent
})
```

## Performance Configuration

### Connection Pooling

```python title="performance.py"
from typing import Generator
# Reuse SSH connections
slurm = submit('cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'user',
    'connection_pool_size': 5,
    'keep_alive_interval': 60
})
```

### Batch Job Submission

```python title="batch_config.py"
from typing import Generator
# Configure for batch operations
slurm = submit('cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'user',
    'batch_size': 10,  # Submit jobs in batches
    'batch_delay': 1.0  # Delay between batches
})
```

## Validation and Testing

### Configuration Validation

```python title="validation.py"
from typing import Generator
from molq import submit

def validate_config():
    try:
        # Test connection
        slurm = submit('test', 'slurm', {
            'host': 'cluster.example.com',
            'username': 'user'
        })
        
        # Submit test job
        @slurm
        def test_job() -> Generator[dict, int, int]:
            job_id = yield {
                'cmd': ['echo', 'test'],
                'job_name': 'config_test',
                'time': '00:01:00',
                'block': True
            }
            return job_id
        
        result = test_job()
        print(f"Configuration valid - test job: {result}")
        
    except Exception as e:
        print(f"Configuration error: {e}")

if __name__ == "__main__":
    validate_config()
```

## Best Practices

### 1. Use Environment-Specific Configurations

```python title="environments.py"
from typing import Generator
import os

# Load configuration based on environment
env = os.environ.get('MOLQ_ENV', 'development')

if env == 'production':
    config = {
        'host': 'prod-cluster.example.com',
        'partition': 'production',
        'account': 'prod_account'
    }
elif env == 'staging':
    config = {
        'host': 'staging-cluster.example.com',
        'partition': 'staging', 
        'account': 'staging_account'
    }
else:
    config = {
        'host': 'dev-cluster.example.com',
        'partition': 'development',
        'account': 'dev_account'
    }

cluster = submit('cluster', 'slurm', config)
```

### 2. Resource Right-Sizing

```python title="resource_sizing.py"
from typing import Generator
# Start with minimal resources
test_config = {
    'cpus_per_task': 1,
    'memory': '1G',
    'time': '00:10:00'
}

# Scale up for production
production_config = {
    'cpus_per_task': 8,
    'memory': '32G', 
    'time': '04:00:00'
}
```

### 3. Error Handling

```python title="error_handling.py"
from typing import Generator
import logging

# Configure comprehensive error handling
slurm = submit('cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'user',
    'retry_attempts': 3,
    'retry_delay': 60,
    'timeout': 300
})

@slurm
def robust_job() -> Generator[dict, int, int]:
    try:
        job_id = yield {
            'cmd': ['python', 'script.py'],
            'job_name': 'robust_job',
            'mail_type': 'FAIL',
            'mail_user': 'admin@example.com'
        }
        return job_id
    except Exception as e:
        logging.error(f"Job submission failed: {e}")
        raise
```

## Next Steps

- Learn about [Decorators](decorators.md) usage patterns
- Explore [SLURM Integration](slurm-integration.md) details
- Check [Examples](../examples/monitoring.md) for monitoring configurations
- Review [API Reference](../api/submitters.md) for all parameters
