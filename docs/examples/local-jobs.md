# Local Jobs Examples

This section provides comprehensive examples of running jobs locally using Molq's local execution capabilities.

## Basic Local Job Execution

### Simple Command Execution

```python title="basic_local.py"
from typing import Generator
from molq import submit

# Create local submitter
local = submit('local_runner', 'local')

@local
def hello_world() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['echo', 'Hello, World!'],
        'job_name': 'hello',
        'block': True
    }
    return job_id

if __name__ == "__main__":
    job_id = hello_world()
    print(f"Job completed with ID: {job_id}")
```

### Python Script Execution

```python title="python_local.py"
from typing import Generator
from molq import submit

local = submit('python_runner', 'local', {
    'working_directory': '/tmp/molq_jobs',
    'environment': {
        'PYTHONPATH': '/path/to/modules'
    }
})

@local
def run_python_script() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', '-c', 'print("Hello from Python!")'],
        'job_name': 'python_job',
        'output_file': 'python_output.log',
        'error_file': 'python_error.log',
        'block': True
    }
    return job_id

if __name__ == "__main__":
    job_id = run_python_script()
    print(f"Python job completed: {job_id}")
```

## Advanced Local Job Patterns

### Parallel Job Execution

```python title="parallel_local.py"
from typing import Generator
import concurrent.futures
from molq import submit

local = submit('parallel_runner', 'local', {
    'max_concurrent_jobs': 4
})

@local
def process_file(filename: str) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'process_data.py', filename],
        'job_name': f'process_{filename}',
        'block': False  # Don't block for parallel execution
    }
    return job_id

def process_multiple_files():
    filenames = ['data1.txt', 'data2.txt', 'data3.txt', 'data4.txt']
    
    # Submit all jobs
    job_ids = []
    for filename in filenames:
        job_id = process_file(filename)
        job_ids.append(job_id)
    
    print(f"Submitted {len(job_ids)} jobs: {job_ids}")
    return job_ids

if __name__ == "__main__":
    jobs = process_multiple_files()
```

### Job Dependencies

```python title="dependencies_local.py"
from typing import Generator
import time
from molq import submit

local = submit('dependency_runner', 'local')

@local
def prepare_data() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'prepare_data.py'],
        'job_name': 'data_preparation',
        'block': True
    }
    return job_id

@local
def analyze_data() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'analyze_data.py'],
        'job_name': 'data_analysis',
        'block': True
    }
    return job_id

@local
def generate_report() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'generate_report.py'],
        'job_name': 'report_generation',
        'block': True
    }
    return job_id

def run_pipeline():
    """Run a complete data processing pipeline"""
    print("Starting data pipeline...")
    
    # Step 1: Prepare data
    prep_job = prepare_data()
    print(f"Data preparation completed: {prep_job}")
    
    # Step 2: Analyze data
    analysis_job = analyze_data()
    print(f"Data analysis completed: {analysis_job}")
    
    # Step 3: Generate report
    report_job = generate_report()
    print(f"Report generation completed: {report_job}")
    
    print("Pipeline completed successfully!")

if __name__ == "__main__":
    run_pipeline()
```

## File Management

### Working with Files

```python title="file_management.py"
from typing import Generator
import os
from molq import submit

local = submit('file_runner', 'local', {
    'working_directory': '/tmp/molq_workspace'
})

@local
def create_and_process_file() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': [
            'bash', '-c',
            '''
            echo "Creating test file..."
            echo "Sample data" > input.txt
            echo "Processing file..."
            wc -l input.txt > output.txt
            echo "File processing complete"
            '''
        ],
        'job_name': 'file_processing',
        'output_file': 'processing.log',
        'block': True
    }
    return job_id

@local
def cleanup_files() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['rm', '-f', 'input.txt', 'output.txt'],
        'job_name': 'cleanup',
        'block': True
    }
    return job_id

def run_file_workflow():
    # Create working directory
    os.makedirs('/tmp/molq_workspace', exist_ok=True)
    
    # Process files
    process_job = create_and_process_file()
    print(f"File processing job: {process_job}")
    
    # Cleanup
    cleanup_job = cleanup_files()
    print(f"Cleanup job: {cleanup_job}")

if __name__ == "__main__":
    run_file_workflow()
```

### Directory Operations

```python title="directory_ops.py"
from typing import Generator
from molq import submit

local = submit('dir_runner', 'local')

@local
def create_project_structure() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': [
            'bash', '-c',
            '''
            mkdir -p project/{src,tests,docs,data}
            touch project/README.md
            touch project/src/__init__.py
            touch project/tests/test_main.py
            echo "Project structure created"
            tree project/
            '''
        ],
        'job_name': 'create_structure',
        'block': True
    }
    return job_id

@local
def archive_project() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['tar', '-czf', 'project.tar.gz', 'project/'],
        'job_name': 'archive',
        'block': True
    }
    return job_id

if __name__ == "__main__":
    # Create project structure
    create_job = create_project_structure()
    print(f"Project creation job: {create_job}")
    
    # Archive project
    archive_job = archive_project()
    print(f"Archive job: {archive_job}")
```

## Environment Management

### Custom Environment Variables

```python title="environment_vars.py"
from typing import Generator
from molq import submit

local = submit('env_runner', 'local', {
    'environment': {
        'GLOBAL_VAR': 'global_value',
        'PYTHONPATH': '/custom/python/path'
    }
})

@local
def job_with_custom_env() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': [
            'bash', '-c',
            '''
            echo "Global variable: $GLOBAL_VAR"
            echo "Job-specific variable: $JOB_VAR"
            echo "Python path: $PYTHONPATH"
            env | grep -E "(GLOBAL|JOB|PYTHON)"
            '''
        ],
        'job_name': 'env_test',
        'environment': {
            'JOB_VAR': 'job_specific_value'
        },
        'block': True
    }
    return job_id

if __name__ == "__main__":
    job_id = job_with_custom_env()
    print(f"Environment test job: {job_id}")
```

### Conda Environment Integration

```python title="conda_local.py"
from typing import Generator
from molq import submit

local = submit('conda_runner', 'local')

@local
def run_with_conda() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': [
            'bash', '-c',
            '''
            source ~/miniconda3/etc/profile.d/conda.sh
            conda activate myenv
            python -c "import sys; print(f'Python: {sys.executable}')"
            python my_script.py
            '''
        ],
        'job_name': 'conda_job',
        'block': True
    }
    return job_id

if __name__ == "__main__":
    job_id = run_with_conda()
    print(f"Conda job: {job_id}")
```

## Monitoring and Logging

### Job Monitoring

```python title="monitoring_local.py"
from typing import Generator
import time
from molq import submit
from molq.submitor import LocalSubmitor

local = submit('monitor_runner', 'local')

@local
def long_running_job() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['sleep', '10'],
        'job_name': 'long_job',
        'block': False  # Don't block to allow monitoring
    }
    return job_id

def monitor_job():
    # Submit job
    job_id = long_running_job()
    print(f"Submitted job: {job_id}")
    
    # Monitor job progress
    submitter = LocalSubmitor({})
    
    while True:
        status = submitter.get_job_status(job_id)
        print(f"Job {job_id} status: {status}")
        
        if status in ['completed', 'failed']:
            break
        
        time.sleep(2)
    
    print(f"Job {job_id} finished with status: {status}")

if __name__ == "__main__":
    monitor_job()
```

### Logging Configuration

```python title="logging_local.py"
from typing import Generator
import logging
from molq import submit

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

local = submit('logging_runner', 'local')

@local
def logged_job() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': [
            'python', '-c',
            '''
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("Job started")
print("Hello from logged job")
logger.info("Job completed")
            '''
        ],
        'job_name': 'logged_job',
        'output_file': 'job_output.log',
        'error_file': 'job_error.log',
        'block': True
    }
    return job_id

if __name__ == "__main__":
    job_id = logged_job()
    print(f"Logged job completed: {job_id}")
```

## Error Handling and Recovery

### Robust Job Execution

```python title="error_handling_local.py"
from typing import Generator
import logging
from molq import submit

local = submit('robust_runner', 'local')

@local
def may_fail_job(should_fail: bool = False) -> Generator[dict, int, int]:
    cmd = ['python', '-c', 'import sys; sys.exit(1)'] if should_fail else ['echo', 'success']
    
    job_id = yield {
        'cmd': cmd,
        'job_name': 'test_job',
        'block': True
    }
    return job_id

def run_with_retry(max_attempts: int = 3):
    for attempt in range(max_attempts):
        try:
            print(f"Attempt {attempt + 1}/{max_attempts}")
            
            # Try with failure first, then success
            should_fail = attempt < max_attempts - 1
            job_id = may_fail_job(should_fail)
            
            print(f"Job succeeded on attempt {attempt + 1}: {job_id}")
            return job_id
            
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_attempts - 1:
                print("All attempts failed")
                raise
            else:
                print("Retrying...")

if __name__ == "__main__":
    try:
        result = run_with_retry()
        print(f"Final result: {result}")
    except Exception as e:
        print(f"Job ultimately failed: {e}")
```

### Exception Handling

```python title="exceptions_local.py"
from typing import Generator
from molq import submit
from molq.exceptions import JobExecutionError, SubmissionError

local = submit('error_runner', 'local')

@local
def risky_job() -> Generator[dict, int, int]:
    try:
        job_id = yield {
            'cmd': ['python', '-c', 'raise ValueError("Test error")'],
            'job_name': 'risky_job',
            'block': True
        }
        return job_id
    except JobExecutionError as e:
        print(f"Job execution failed: {e}")
        raise
    except SubmissionError as e:
        print(f"Job submission failed: {e}")
        raise

if __name__ == "__main__":
    try:
        job_id = risky_job()
        print(f"Job completed: {job_id}")
    except Exception as e:
        print(f"Job failed: {e}")
```

## Performance Optimization

### Resource Management

```python title="resource_management.py"
from typing import Generator
import psutil
from molq import submit

# Configure based on system resources
cpu_count = psutil.cpu_count()
memory_gb = psutil.virtual_memory().total // (1024**3)

local = submit('optimized_runner', 'local', {
    'max_concurrent_jobs': cpu_count,
    'environment': {
        'OMP_NUM_THREADS': str(cpu_count // 2)
    }
})

@local
def cpu_intensive_job() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': [
            'python', '-c',
            f'''
import multiprocessing
import time

def cpu_task():
    # Simulate CPU-intensive work
    total = 0
    for i in range(1000000):
        total += i ** 2
    return total

# Use available CPUs
with multiprocessing.Pool({cpu_count}) as pool:
    results = pool.map(cpu_task, range({cpu_count}))
    print(f"Processed {len(results)} tasks")
            '''
        ],
        'job_name': 'cpu_job',
        'block': True
    }
    return job_id

if __name__ == "__main__":
    print(f"System: {cpu_count} CPUs, {memory_gb} GB RAM")
    job_id = cpu_intensive_job()
    print(f"CPU-intensive job completed: {job_id}")
```

### Batch Processing

```python title="batch_processing.py"
from typing import Generator
import glob
from molq import submit

local = submit('batch_runner', 'local', {
    'max_concurrent_jobs': 3
})

@local
def process_batch(batch_files: list) -> Generator[dict, int, int]:
    files_str = ' '.join(batch_files)
    job_id = yield {
        'cmd': ['python', 'batch_processor.py'] + batch_files,
        'job_name': f'batch_{len(batch_files)}_files',
        'block': False
    }
    return job_id

def process_all_files():
    # Get all files to process
    all_files = glob.glob('data/*.txt')
    batch_size = 5
    
    # Process files in batches
    job_ids = []
    for i in range(0, len(all_files), batch_size):
        batch = all_files[i:i + batch_size]
        job_id = process_batch(batch)
        job_ids.append(job_id)
        print(f"Submitted batch {len(job_ids)}: {batch}")
    
    print(f"Submitted {len(job_ids)} batch jobs")
    return job_ids

if __name__ == "__main__":
    jobs = process_all_files()
```

## Integration with Hamilton

### Hamilton Dataflow with Local Jobs

```python title="hamilton_local.py"
from typing import Generator
import hamilton.driver
from molq import submit

local = submit('hamilton_local', 'local', {
    'working_directory': '/tmp/hamilton_jobs'
})

# Hamilton functions with local job execution
@local
def data_extraction(source_file: str) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'extract_data.py', source_file],
        'job_name': 'data_extraction',
        'output_file': 'extraction.log',
        'block': True
    }
    return job_id

@local
def data_transformation(extraction_job_id: int) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'transform_data.py'],
        'job_name': 'data_transformation',
        'output_file': 'transformation.log',
        'block': True
    }
    return job_id

@local
def data_loading(transformation_job_id: int) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'load_data.py'],
        'job_name': 'data_loading',
        'output_file': 'loading.log',
        'block': True
    }
    return job_id

def run_etl_pipeline():
    """Run ETL pipeline using Hamilton with local jobs"""
    
    # Create Hamilton driver
    dr = hamilton.driver.Driver(
        {},
        data_extraction,
        data_transformation,
        data_loading
    )
    
    # Execute the pipeline
    results = dr.execute(
        ['data_loading'],
        inputs={'source_file': 'raw_data.csv'}
    )
    
    print(f"ETL Pipeline Results: {results}")
    return results

if __name__ == "__main__":
    results = run_etl_pipeline()
```

## Testing Local Jobs

### Unit Testing

```python title="test_local_jobs.py"
from typing import Generator
import unittest
from unittest.mock import patch, MagicMock
from molq import submit

class TestLocalJobs(unittest.TestCase):
    def setUp(self):
        self.local = submit('test_runner', 'local')
    
    def test_simple_job(self):
        @self.local
        def test_job() -> Generator[dict, int, int]:
            job_id = yield {
                'cmd': ['echo', 'test'],
                'job_name': 'test',
                'block': True
            }
            return job_id
        
        result = test_job()
        self.assertIsInstance(result, int)
        self.assertGreater(result, 0)
    
    @patch('molq.submitor.local.subprocess.run')
    def test_mocked_job(self, mock_run):
        # Mock subprocess.run
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.pid = 12345
        mock_run.return_value = mock_process
        
        @self.local
        def mocked_job() -> Generator[dict, int, int]:
            job_id = yield {
                'cmd': ['echo', 'mocked'],
                'job_name': 'mocked_test',
                'block': True
            }
            return job_id
        
        result = mocked_job()
        self.assertEqual(result, 12345)
        mock_run.assert_called_once()

if __name__ == "__main__":
    unittest.main()
```

### Integration Testing

```python title="integration_test_local.py"
from typing import Generator
import tempfile
import os
from molq import submit

def test_file_processing_integration():
    """Integration test for file processing workflow"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Configure local submitter with temp directory
        local = submit('integration_test', 'local', {
            'working_directory': temp_dir
        })
        
        # Create test input file
        input_file = os.path.join(temp_dir, 'input.txt')
        with open(input_file, 'w') as f:
            f.write('line 1\nline 2\nline 3\n')
        
        @local
        def count_lines() -> Generator[dict, int, int]:
            job_id = yield {
                'cmd': ['wc', '-l', 'input.txt'],
                'job_name': 'count_lines',
                'output_file': 'output.txt',
                'block': True
            }
            return job_id
        
        # Run the job
        job_id = count_lines()
        
        # Verify output
        output_file = os.path.join(temp_dir, 'output.txt')
        assert os.path.exists(output_file)
        
        with open(output_file, 'r') as f:
            output = f.read().strip()
            assert '3' in output  # Should contain line count
        
        print("Integration test passed!")

if __name__ == "__main__":
    test_file_processing_integration()
```

## Best Practices

### 1. Resource Awareness

```python title="resource_aware.py"
from typing import Generator
import os
import psutil
from molq import submit

# Detect system capabilities
cpu_cores = os.cpu_count()
memory_gb = psutil.virtual_memory().total // (1024**3)

# Configure appropriately
local = submit('resource_aware', 'local', {
    'max_concurrent_jobs': min(cpu_cores, 4),  # Don't overwhelm system
    'environment': {
        'OMP_NUM_THREADS': str(max(1, cpu_cores // 2))
    }
})
```

### 2. Proper Error Handling

```python title="best_practices.py"
from typing import Generator
import logging
from molq import submit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

local = submit('best_practices', 'local')

@local
def robust_job(input_file: str) -> Generator[dict, int, int]:
    # Validate inputs
    if not os.path.exists(input_file):
        raise ValueError(f"Input file not found: {input_file}")
    
    try:
        job_id = yield {
            'cmd': ['python', 'process.py', input_file],
            'job_name': f'process_{os.path.basename(input_file)}',
            'output_file': f'{input_file}.log',
            'error_file': f'{input_file}.err',
            'block': True
        }
        logger.info(f"Job completed successfully: {job_id}")
        return job_id
    except Exception as e:
        logger.error(f"Job failed: {e}")
        raise
```

### 3. Clean Resource Management

```python title="resource_cleanup.py"
from typing import Generator
import tempfile
import shutil
from contextlib import contextmanager
from molq import submit

@contextmanager
def managed_workspace():
    """Context manager for temporary workspace"""
    temp_dir = tempfile.mkdtemp(prefix='molq_')
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def clean_job_execution():
    with managed_workspace() as workspace:
        local = submit('clean_runner', 'local', {
            'working_directory': workspace
        })
        
        @local
        def clean_job() -> Generator[dict, int, int]:
            job_id = yield {
                'cmd': ['echo', 'Clean execution'],
                'job_name': 'clean_job',
                'block': True
            }
            return job_id
        
        result = clean_job()
        print(f"Job completed in clean workspace: {result}")
        # Workspace automatically cleaned up

if __name__ == "__main__":
    clean_job_execution()
```

## Next Steps

- Learn about [SLURM Jobs](slurm-jobs.md) for cluster execution
- Explore [Command Line](cmdline.md) examples
- Check [Monitoring](monitoring.md) for job tracking
- Review [API Reference](../api/submitters.md) for detailed parameters
