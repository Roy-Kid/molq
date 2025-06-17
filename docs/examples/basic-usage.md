# Basic Usage Examples

This page provides practical examples of using Molq for job submission and management.

## Simple Job Submission

### Local Job Execution

```python
from molq import submit
from molq.resources import BaseResourceSpec

# Create a local submitter
local = submit('my_project', 'local')

@local
def hello_world():
    """Submit a simple hello world job."""
    spec = BaseResourceSpec(
        cmd=['echo', 'Hello, World!'],
        job_name='hello-world'
    )
    job_id = yield spec.model_dump()
    return job_id

# Submit the job
job_id = hello_world()
print(f"Job submitted with ID: {job_id}")
```

### SLURM Job Execution

```python
from molq import submit
from molq.resources import BaseResourceSpec

# Create a SLURM submitter
slurm = submit('my_project', 'slurm')

@slurm
def data_processing():
    """Submit a data processing job to SLURM."""
    spec = BaseResourceSpec(
        cmd=['python', 'process_data.py', '--input', 'dataset.csv'],
        job_name='data-processing',
        cpu_count=8,
        memory='16GB',
        time_limit='2:00:00',
        queue='normal'
    )
    job_id = yield spec.model_dump()
    return job_id

# Submit the job
job_id = data_processing()
print(f"SLURM job submitted with ID: {job_id}")
```

## Resource Specification

### CPU and Memory

```python
@local
def cpu_intensive_job():
    """Submit a CPU-intensive job with memory requirements."""
    spec = BaseResourceSpec(
        cmd=['python', 'compute_pi.py', '--precision', '1000000'],
        job_name='pi-computation',
        cpu_count=4,          # Request 4 CPU cores
        memory='8GB'          # Request 8GB of memory
    )
    job_id = yield spec.model_dump()
    return job_id
```

### GPU Jobs

```python
@slurm
def gpu_training():
    """Submit a GPU training job."""
    spec = BaseResourceSpec(
        cmd=['python', 'train_model.py'],
        job_name='gpu-training',
        cpu_count=4,
        memory='32GB',
        gpu_count=2,          # Request 2 GPUs
        gpu_type='V100',      # Specific GPU type
        time_limit='12:00:00'
    )
    job_id = yield spec.model_dump()
    return job_id
```

## Working with Files and Directories

### Setting Working Directory

```python
@local
def build_project():
    """Build a project in a specific directory."""
    spec = BaseResourceSpec(
        cmd=['make', 'build'],
        job_name='project-build',
        work_dir='/path/to/project'  # Set working directory
    )
    job_id = yield spec.model_dump()
    return job_id
```

### File Processing Pipeline

```python
@local
def process_files():
    """Process multiple files in sequence."""
    spec = BaseResourceSpec(
        cmd=[
            'bash', '-c',
            'for file in *.txt; do python process.py "$file"; done'
        ],
        job_name='file-processing',
        work_dir='/data/input'
    )
    job_id = yield spec.model_dump()
    return job_id
```

## Environment Management

### Conda Environment

```python
@local
def conda_job():
    """Run a job in a specific Conda environment."""
    spec = BaseResourceSpec(
        cmd=['python', 'analysis.py'],
        job_name='conda-analysis',
        conda_env='data-science'  # Activate conda environment
    )
    job_id = yield spec.model_dump()
    return job_id
```

### Environment Variables

```python
@local
def env_job():
    """Job with custom environment variables."""
    spec = BaseResourceSpec(
        cmd=['python', 'app.py'],
        job_name='env-job',
        env_vars={
            'API_KEY': 'your-api-key',
            'DEBUG': 'true',
            'WORKERS': '4'
        }
    )
    job_id = yield spec.model_dump()
    return job_id
```

## Job Arrays and Batch Processing

### Parameter Sweep

```python
@slurm
def parameter_sweep():
    """Submit multiple jobs with different parameters."""
    parameters = [
        {'lr': 0.001, 'batch_size': 32},
        {'lr': 0.01, 'batch_size': 64},
        {'lr': 0.1, 'batch_size': 128}
    ]
    
    job_ids = []
    for i, params in enumerate(parameters):
        spec = BaseResourceSpec(
            cmd=[
                'python', 'train.py',
                '--learning-rate', str(params['lr']),
                '--batch-size', str(params['batch_size'])
            ],
            job_name=f'training-{i}',
            cpu_count=2,
            memory='8GB'
        )
        job_id = yield spec.model_dump()
        job_ids.append(job_id)
    
    return job_ids
```

## Error Handling and Monitoring

### Job with Error Handling

```python
@local
def robust_job():
    """Job with built-in error handling."""
    spec = BaseResourceSpec(
        cmd=[
            'bash', '-c',
            '''
            set -e  # Exit on error
            echo "Starting job..."
            python main.py || {
                echo "Job failed, cleaning up..."
                rm -f temp_files/*
                exit 1
            }
            echo "Job completed successfully"
            '''
        ],
        job_name='robust-job',
        cleanup_temp_files=True
    )
    job_id = yield spec.model_dump()
    return job_id
```

### Blocking Job Execution

```python
@local
def blocking_job():
    """Wait for job completion before continuing."""
    spec = BaseResourceSpec(
        cmd=['python', 'long_running_task.py'],
        job_name='blocking-task',
        block=True  # Wait for completion
    )
    job_id = yield spec.model_dump()
    print("Job completed!")
    return job_id
```

## Integration with Hamilton

### Hamilton Dataflow Example

```python
import pandas as pd
from hamilton import function_modifiers
from molq import submit

# Create submitter
local = submit('data_pipeline', 'local')

def load_data() -> pd.DataFrame:
    """Load initial dataset."""
    return pd.read_csv('input.csv')

@local
@function_modifiers.extract_columns('processed_data')
def process_data(load_data: pd.DataFrame) -> pd.DataFrame:
    """Process data using a remote job."""
    # Save input data temporarily
    input_file = 'temp_input.csv'
    load_data.to_csv(input_file, index=False)
    
    spec = BaseResourceSpec(
        cmd=['python', 'data_processor.py', input_file, 'temp_output.csv'],
        job_name='data-processing',
        block=True  # Wait for completion
    )
    job_id = yield spec.model_dump()
    
    # Load processed results
    return pd.read_csv('temp_output.csv')

def analyze_results(processed_data: pd.DataFrame) -> dict:
    """Analyze the processed data."""
    return {
        'mean': processed_data.mean().to_dict(),
        'std': processed_data.std().to_dict(),
        'count': len(processed_data)
    }
```

## Best Practices

### Resource Estimation

```python
@slurm
def optimized_job():
    """Job with properly estimated resources."""
    spec = BaseResourceSpec(
        cmd=['python', 'heavy_computation.py'],
        job_name='optimized-job',
        # Conservative resource estimates
        cpu_count=8,          # Based on profiling
        memory='32GB',        # 20% buffer over measured usage
        time_limit='4:00:00', # 50% buffer over typical runtime
        queue='normal'        # Appropriate queue for job size
    )
    job_id = yield spec.model_dump()
    return job_id
```

### Job Naming Convention

```python
@local
def well_named_job():
    """Use descriptive job names."""
    import datetime
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    spec = BaseResourceSpec(
        cmd=['python', 'analysis.py'],
        job_name=f'analysis_{timestamp}',  # Include timestamp
        # Alternative: include parameters in name
        # job_name=f'analysis_lr0.01_bs64_{timestamp}'
    )
    job_id = yield spec.model_dump()
    return job_id
```

### Cleanup and Maintenance

```python
@local
def clean_job():
    """Job that cleans up after itself."""
    spec = BaseResourceSpec(
        cmd=[
            'bash', '-c',
            '''
            # Your main computation
            python main_computation.py
            
            # Cleanup temporary files
            rm -f temp_*
            rm -rf scratch_dir/
            
            # Archive results
            tar -czf results_$(date +%Y%m%d).tar.gz results/
            '''
        ],
        job_name='clean-computation',
        cleanup_temp_files=True
    )
    job_id = yield spec.model_dump()
    return job_id
```
