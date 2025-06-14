# SLURM Jobs Examples

This section provides comprehensive examples of submitting and managing jobs on SLURM clusters using Molq.

## Basic SLURM Job Submission

### Simple Job Submission

```python title="basic_slurm.py"
from typing import Generator
from molq import submit

# Configure SLURM cluster
slurm = submit('hpc_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'your_username',
    'ssh_key_path': '~/.ssh/id_rsa',
    'partition': 'compute'
})

@slurm
def hello_slurm() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['echo', 'Hello from SLURM!'],
        'job_name': 'hello_slurm',
        'output_file': 'hello_%j.out',
        'error_file': 'hello_%j.err',
        'time': '00:05:00',
        'cpus_per_task': 1,
        'memory': '1G',
        'block': False
    }
    return job_id

if __name__ == "__main__":
    job_id = hello_slurm()
    print(f"Submitted SLURM job: {job_id}")
```

### Python Script on SLURM

```python title="python_slurm.py"
from typing import Generator
from molq import submit

slurm = submit('python_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'researcher',
    'partition': 'compute',
    'account': 'research_project'
})

@slurm
def python_computation() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'compute_pi.py', '--precision', '1000'],
        'job_name': 'pi_computation',
        'output_file': 'pi_computation_%j.out',
        'error_file': 'pi_computation_%j.err',
        'cpus_per_task': 4,
        'memory': '8G',
        'time': '01:00:00',
        'mail_type': 'END,FAIL',
        'mail_user': 'researcher@university.edu',
        'block': False
    }
    return job_id

if __name__ == "__main__":
    job_id = python_computation()
    print(f"Pi computation job submitted: {job_id}")
```

## Resource Management

### CPU-Intensive Jobs

```python title="cpu_intensive.py"
from typing import Generator
from molq import submit

slurm = submit('compute_cluster', 'slurm', {
    'host': 'hpc.university.edu',
    'username': 'researcher',
    'partition': 'cpu',
    'account': 'research_account'
})

@slurm
def cpu_benchmark() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'cpu_benchmark.py'],
        'job_name': 'cpu_benchmark',
        'cpus_per_task': 16,
        'memory': '32G',
        'time': '04:00:00',
        'output_file': 'benchmark_%j.out',
        'error_file': 'benchmark_%j.err',
        'block': False
    }
    return job_id

@slurm
def parallel_computation() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['mpirun', '-n', '32', './parallel_app'],
        'job_name': 'parallel_comp',
        'nodes': 2,
        'ntasks_per_node': 16,
        'cpus_per_task': 1,
        'memory_per_cpu': '2G',
        'time': '08:00:00',
        'partition': 'mpi',
        'block': False
    }
    return job_id

if __name__ == "__main__":
    # Submit different types of compute jobs
    benchmark_job = cpu_benchmark()
    parallel_job = parallel_computation()
    
    print(f"CPU benchmark: {benchmark_job}")
    print(f"Parallel computation: {parallel_job}")
```

### GPU Jobs

```python title="gpu_jobs.py"
from typing import Generator
from molq import submit

gpu_cluster = submit('gpu_cluster', 'slurm', {
    'host': 'gpu-cluster.example.com',
    'username': 'ml_researcher',
    'partition': 'gpu',
    'account': 'ml_project'
})

@gpu_cluster
def train_model() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'train_model.py', '--epochs', '100'],
        'job_name': 'model_training',
        'gres': 'gpu:tesla:2',  # Request 2 Tesla GPUs
        'cpus_per_task': 8,
        'memory': '64G',
        'time': '24:00:00',
        'output_file': 'training_%j.out',
        'error_file': 'training_%j.err',
        'mail_type': 'END,FAIL',
        'mail_user': 'ml_researcher@university.edu',
        'block': False
    }
    return job_id

@gpu_cluster
def inference_job() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'run_inference.py', '--batch-size', '32'],
        'job_name': 'model_inference',
        'gres': 'gpu:1',  # Single GPU for inference
        'cpus_per_task': 4,
        'memory': '16G',
        'time': '02:00:00',
        'output_file': 'inference_%j.out',
        'error_file': 'inference_%j.err',
        'block': False
    }
    return job_id

if __name__ == "__main__":
    training_job = train_model()
    inference_job_id = inference_job()
    
    print(f"Training job: {training_job}")
    print(f"Inference job: {inference_job_id}")
```

### Memory-Intensive Jobs

```python title="memory_intensive.py"
from typing import Generator
from molq import submit

highmem_cluster = submit('highmem_cluster', 'slurm', {
    'host': 'bigmem.cluster.edu',
    'username': 'data_scientist',
    'partition': 'highmem',
    'account': 'data_project'
})

@highmem_cluster
def large_dataset_analysis() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'analyze_large_data.py', '--dataset', 'huge_dataset.h5'],
        'job_name': 'large_analysis',
        'memory': '256G',
        'cpus_per_task': 16,
        'time': '12:00:00',
        'output_file': 'analysis_%j.out',
        'error_file': 'analysis_%j.err',
        'constraint': 'bigmem',  # Require big memory nodes
        'block': False
    }
    return job_id

@highmem_cluster
def genome_assembly() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['./genome_assembler', '--input', 'reads.fastq', '--output', 'assembly.fasta'],
        'job_name': 'genome_assembly',
        'memory': '512G',
        'cpus_per_task': 32,
        'time': '48:00:00',
        'output_file': 'assembly_%j.out',
        'error_file': 'assembly_%j.err',
        'partition': 'bigmem',
        'block': False
    }
    return job_id

if __name__ == "__main__":
    analysis_job = large_dataset_analysis()
    assembly_job = genome_assembly()
    
    print(f"Large dataset analysis: {analysis_job}")
    print(f"Genome assembly: {assembly_job}")
```

## Job Arrays and Batch Processing

### Job Arrays

```python title="job_arrays.py"
from typing import Generator
from molq import submit

slurm = submit('array_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'researcher',
    'partition': 'compute'
})

@slurm
def parameter_sweep() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'parameter_study.py', '--param-id', '$SLURM_ARRAY_TASK_ID'],
        'job_name': 'param_sweep',
        'array': '1-100',  # Create 100 jobs
        'cpus_per_task': 2,
        'memory': '4G',
        'time': '02:00:00',
        'output_file': 'param_sweep_%A_%a.out',
        'error_file': 'param_sweep_%A_%a.err',
        'block': False
    }
    return job_id

@slurm
def batch_processing() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'process_batch.py', '--batch-id', '$SLURM_ARRAY_TASK_ID'],
        'job_name': 'batch_proc',
        'array': '1-50%10',  # 50 jobs, max 10 running simultaneously
        'cpus_per_task': 4,
        'memory': '8G',
        'time': '01:30:00',
        'output_file': 'batch_%A_%a.out',
        'error_file': 'batch_%A_%a.err',
        'block': False
    }
    return job_id

if __name__ == "__main__":
    sweep_job = parameter_sweep()
    batch_job = batch_processing()
    
    print(f"Parameter sweep job array: {sweep_job}")
    print(f"Batch processing job array: {batch_job}")
```

### File-Based Batch Processing

```python title="file_batch.py"
from typing import Generator
import glob
from molq import submit

slurm = submit('file_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'researcher',
    'partition': 'compute'
})

def create_file_list():
    """Create a file list for batch processing"""
    files = glob.glob('/data/input/*.txt')
    with open('file_list.txt', 'w') as f:
        for i, file_path in enumerate(files, 1):
            f.write(f"{i}\t{file_path}\n")
    return len(files)

@slurm
def process_file_batch(num_files: int) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': [
            'bash', '-c',
            '''
            LINE=$(sed -n "${SLURM_ARRAY_TASK_ID}p" file_list.txt)
            FILE_PATH=$(echo $LINE | cut -f2)
            echo "Processing file: $FILE_PATH"
            python process_file.py "$FILE_PATH"
            '''
        ],
        'job_name': 'file_processing',
        'array': f'1-{num_files}',
        'cpus_per_task': 2,
        'memory': '4G',
        'time': '01:00:00',
        'output_file': 'file_proc_%A_%a.out',
        'error_file': 'file_proc_%A_%a.err',
        'block': False
    }
    return job_id

if __name__ == "__main__":
    # Create file list and submit batch job
    num_files = create_file_list()
    job_id = process_file_batch(num_files)
    print(f"Submitted batch processing for {num_files} files: {job_id}")
```

## Job Dependencies

### Sequential Dependencies

```python title="sequential_deps.py"
from typing import Generator
from molq import submit

slurm = submit('dep_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'researcher',
    'partition': 'compute'
})

@slurm
def data_preparation() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'prepare_data.py'],
        'job_name': 'data_prep',
        'cpus_per_task': 4,
        'memory': '16G',
        'time': '02:00:00',
        'output_file': 'data_prep_%j.out',
        'error_file': 'data_prep_%j.err',
        'block': False
    }
    return job_id

@slurm
def model_training(prep_job_id: int) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'train_model.py'],
        'job_name': 'model_training',
        'dependency': f'afterok:{prep_job_id}',
        'gres': 'gpu:2',
        'cpus_per_task': 8,
        'memory': '32G',
        'time': '12:00:00',
        'output_file': 'training_%j.out',
        'error_file': 'training_%j.err',
        'block': False
    }
    return job_id

@slurm
def model_evaluation(training_job_id: int) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'evaluate_model.py'],
        'job_name': 'model_eval',
        'dependency': f'afterok:{training_job_id}',
        'cpus_per_task': 4,
        'memory': '8G',
        'time': '01:00:00',
        'output_file': 'evaluation_%j.out',
        'error_file': 'evaluation_%j.err',
        'block': False
    }
    return job_id

def run_ml_pipeline():
    """Run machine learning pipeline with dependencies"""
    print("Starting ML pipeline...")
    
    # Submit jobs in sequence
    prep_job = data_preparation()
    print(f"Data preparation job: {prep_job}")
    
    training_job = model_training(prep_job)
    print(f"Model training job: {training_job}")
    
    eval_job = model_evaluation(training_job)
    print(f"Model evaluation job: {eval_job}")
    
    print("ML pipeline submitted successfully!")

if __name__ == "__main__":
    run_ml_pipeline()
```

### Complex Dependencies

```python title="complex_deps.py"
from typing import Generator
from molq import submit

slurm = submit('complex_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'researcher',
    'partition': 'compute'
})

@slurm
def preprocess_data(dataset_id: int) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'preprocess.py', '--dataset', str(dataset_id)],
        'job_name': f'preprocess_{dataset_id}',
        'cpus_per_task': 2,
        'memory': '8G',
        'time': '01:00:00',
        'block': False
    }
    return job_id

@slurm
def merge_datasets(prep_job_ids: list) -> Generator[dict, int, int]:
    dependencies = ':'.join(map(str, prep_job_ids))
    job_id = yield {
        'cmd': ['python', 'merge_datasets.py'],
        'job_name': 'merge_data',
        'dependency': f'afterok:{dependencies}',
        'cpus_per_task': 4,
        'memory': '16G',
        'time': '00:30:00',
        'block': False
    }
    return job_id

@slurm
def cross_validation(merge_job_id: int, fold: int) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'cross_validate.py', '--fold', str(fold)],
        'job_name': f'cv_fold_{fold}',
        'dependency': f'afterok:{merge_job_id}',
        'cpus_per_task': 8,
        'memory': '32G',
        'time': '04:00:00',
        'block': False
    }
    return job_id

@slurm
def final_evaluation(cv_job_ids: list) -> Generator[dict, int, int]:
    dependencies = ':'.join(map(str, cv_job_ids))
    job_id = yield {
        'cmd': ['python', 'final_evaluation.py'],
        'job_name': 'final_eval',
        'dependency': f'afterok:{dependencies}',
        'cpus_per_task': 4,
        'memory': '16G',
        'time': '01:00:00',
        'block': False
    }
    return job_id

def run_complex_pipeline():
    """Run complex ML pipeline with multiple dependencies"""
    print("Starting complex ML pipeline...")
    
    # Step 1: Preprocess multiple datasets in parallel
    datasets = [1, 2, 3, 4, 5]
    prep_jobs = []
    for dataset_id in datasets:
        job_id = preprocess_data(dataset_id)
        prep_jobs.append(job_id)
        print(f"Preprocessing dataset {dataset_id}: {job_id}")
    
    # Step 2: Merge all preprocessed datasets
    merge_job = merge_datasets(prep_jobs)
    print(f"Merge datasets job: {merge_job}")
    
    # Step 3: Run cross-validation folds in parallel
    folds = [1, 2, 3, 4, 5]
    cv_jobs = []
    for fold in folds:
        job_id = cross_validation(merge_job, fold)
        cv_jobs.append(job_id)
        print(f"Cross-validation fold {fold}: {job_id}")
    
    # Step 4: Final evaluation after all CV folds complete
    final_job = final_evaluation(cv_jobs)
    print(f"Final evaluation job: {final_job}")
    
    print("Complex pipeline submitted successfully!")

if __name__ == "__main__":
    run_complex_pipeline()
```

## Environment and Module Management

### Environment Modules

```python title="modules.py"
from typing import Generator
from molq import submit

slurm = submit('module_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'researcher',
    'partition': 'compute'
})

@slurm
def job_with_modules() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': [
            'bash', '-c',
            '''
            module purge
            module load python/3.9.0 gcc/9.3.0 openmpi/4.1.0
            module list
            
            echo "Running Python computation..."
            python computation.py
            
            echo "Running compiled program..."
            mpirun -n 4 ./mpi_program
            '''
        ],
        'job_name': 'module_job',
        'cpus_per_task': 4,
        'memory': '8G',
        'time': '02:00:00',
        'output_file': 'module_job_%j.out',
        'error_file': 'module_job_%j.err',
        'block': False
    }
    return job_id

@slurm
def bioinformatics_pipeline() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': [
            'bash', '-c',
            '''
            # Load bioinformatics modules
            module load bioinfo-tools
            module load bwa/0.7.17
            module load samtools/1.12
            module load bcftools/1.12
            
            # Run bioinformatics pipeline
            echo "Aligning reads..."
            bwa mem reference.fa reads.fastq > alignment.sam
            
            echo "Converting to BAM..."
            samtools view -bS alignment.sam | samtools sort -o alignment.bam
            
            echo "Calling variants..."
            bcftools mpileup -f reference.fa alignment.bam | bcftools call -mv -o variants.vcf
            
            echo "Pipeline completed"
            '''
        ],
        'job_name': 'bioinfo_pipeline',
        'cpus_per_task': 8,
        'memory': '32G',
        'time': '06:00:00',
        'output_file': 'bioinfo_%j.out',
        'error_file': 'bioinfo_%j.err',
        'block': False
    }
    return job_id

if __name__ == "__main__":
    module_job = job_with_modules()
    bioinfo_job = bioinformatics_pipeline()
    
    print(f"Module job: {module_job}")
    print(f"Bioinformatics pipeline: {bioinfo_job}")
```

### Conda Environments

```python title="conda_slurm.py"
from typing import Generator
from molq import submit

slurm = submit('conda_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'researcher',
    'partition': 'compute'
})

@slurm
def conda_job() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': [
            'bash', '-c',
            '''
            # Initialize conda
            source ~/miniconda3/etc/profile.d/conda.sh
            
            # Activate environment
            conda activate myenv
            
            # Show environment info
            conda info --envs
            conda list
            
            # Run Python script
            python analysis.py
            
            # Deactivate environment
            conda deactivate
            '''
        ],
        'job_name': 'conda_analysis',
        'cpus_per_task': 4,
        'memory': '16G',
        'time': '02:00:00',
        'output_file': 'conda_job_%j.out',
        'error_file': 'conda_job_%j.err',
        'block': False
    }
    return job_id

@slurm
def create_conda_env() -> Generator[dict, int, int]:
    """Create a new conda environment on the cluster"""
    job_id = yield {
        'cmd': [
            'bash', '-c',
            '''
            source ~/miniconda3/etc/profile.d/conda.sh
            
            # Create new environment
            conda create -n analysis_env python=3.9 -y
            
            # Activate and install packages
            conda activate analysis_env
            conda install numpy pandas matplotlib seaborn scikit-learn -y
            pip install additional_package
            
            # Export environment
            conda env export > analysis_env.yml
            
            echo "Environment created successfully"
            '''
        ],
        'job_name': 'create_env',
        'cpus_per_task': 2,
        'memory': '4G',
        'time': '00:30:00',
        'output_file': 'create_env_%j.out',
        'error_file': 'create_env_%j.err',
        'block': False
    }
    return job_id

if __name__ == "__main__":
    env_job = create_conda_env()
    analysis_job = conda_job()
    
    print(f"Environment creation: {env_job}")
    print(f"Conda analysis job: {analysis_job}")
```

## File Transfer and Staging

### Automatic File Staging

```python title="file_staging.py"
from typing import Generator
from molq import submit

slurm = submit('staging_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'researcher',
    'partition': 'compute'
})

@slurm
def job_with_staging() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': [
            'bash', '-c',
            '''
            # List staged files
            echo "Staged input files:"
            ls -la input/
            
            # Process files
            python process_files.py input/ output/
            
            # List output files
            echo "Generated output files:"
            ls -la output/
            '''
        ],
        'job_name': 'staged_job',
        'cpus_per_task': 4,
        'memory': '16G',
        'time': '02:00:00',
        'work_dir': '/scratch/$USER/job_$SLURM_JOB_ID',
        'input_files': [
            '/home/user/data/input1.txt',
            '/home/user/data/input2.txt',
            '/home/user/scripts/process_files.py'
        ],
        'output_files': [
            'output/results.txt',
            'output/plots/*.png'
        ],
        'output_file': 'staged_job_%j.out',
        'error_file': 'staged_job_%j.err',
        'block': False
    }
    return job_id

@slurm
def large_file_transfer() -> Generator[dict, int, int]:
    """Handle large file transfers efficiently"""
    job_id = yield {
        'cmd': [
            'bash', '-c',
            '''
            # Create staging directories
            mkdir -p /scratch/$USER/large_data
            
            # Transfer large files
            echo "Transferring large dataset..."
            rsync -av --progress /data/large_dataset/ /scratch/$USER/large_data/
            
            # Process data
            cd /scratch/$USER/large_data
            python analyze_large_data.py
            
            # Transfer results back
            rsync -av --progress results/ /home/$USER/results/
            
            # Cleanup
            rm -rf /scratch/$USER/large_data
            '''
        ],
        'job_name': 'large_transfer',
        'cpus_per_task': 2,
        'memory': '8G',
        'time': '04:00:00',
        'output_file': 'transfer_%j.out',
        'error_file': 'transfer_%j.err',
        'block': False
    }
    return job_id

if __name__ == "__main__":
    staging_job = job_with_staging()
    transfer_job = large_file_transfer()
    
    print(f"Staged job: {staging_job}")
    print(f"Large file transfer: {transfer_job}")
```

## Monitoring and Troubleshooting

### Job Monitoring

```python title="monitoring.py"
from typing import Generator
import time
from molq import submit
from molq.submitor import SlurmSubmitor

slurm = submit('monitor_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'researcher',
    'partition': 'compute'
})

@slurm
def monitored_job() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'long_running_job.py'],
        'job_name': 'monitored_job',
        'cpus_per_task': 4,
        'memory': '16G',
        'time': '02:00:00',
        'output_file': 'monitored_%j.out',
        'error_file': 'monitored_%j.err',
        'block': False
    }
    return job_id

def monitor_job(job_id: int, submitter: SlurmSubmitor):
    """Monitor job progress"""
    print(f"Monitoring job {job_id}...")
    
    while True:
        try:
            status = submitter.get_job_status(job_id)
            job_info = submitter.get_job_info(job_id)
            
            print(f"Job {job_id}: {status}")
            if job_info:
                print(f"  Start time: {job_info.get('start_time', 'N/A')}")
                print(f"  Node: {job_info.get('node', 'N/A')}")
                print(f"  Elapsed time: {job_info.get('elapsed_time', 'N/A')}")
            
            if status in ['COMPLETED', 'FAILED', 'CANCELLED']:
                break
            
            time.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            print(f"Error monitoring job: {e}")
            break
    
    print(f"Job {job_id} finished with status: {status}")

def main():
    # Submit job
    job_id = monitored_job()
    print(f"Submitted job: {job_id}")
    
    # Monitor job
    submitter = SlurmSubmitor({
        'host': 'cluster.example.com',
        'username': 'researcher'
    })
    
    monitor_job(job_id, submitter)

if __name__ == "__main__":
    main()
```

### Debugging Failed Jobs

```python title="debugging.py"
from typing import Generator
from molq import submit
from molq.submitor import SlurmSubmitor

slurm = submit('debug_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'researcher',
    'partition': 'compute'
})

@slurm
def debug_job() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': [
            'bash', '-c',
            '''
            # Enable debug mode
            set -x
            
            # Print environment
            echo "=== Environment ==="
            env | sort
            
            # Print system info
            echo "=== System Info ==="
            hostname
            whoami
            pwd
            df -h
            free -h
            
            # Print module info
            echo "=== Modules ==="
            module list
            
            # Run actual job
            echo "=== Running Job ==="
            python debug_script.py
            
            echo "=== Job Complete ==="
            '''
        ],
        'job_name': 'debug_job',
        'cpus_per_task': 1,
        'memory': '4G',
        'time': '00:30:00',
        'output_file': 'debug_%j.out',
        'error_file': 'debug_%j.err',
        'verbose': True,
        'block': False
    }
    return job_id

def analyze_failed_job(job_id: int):
    """Analyze a failed job"""
    submitter = SlurmSubmitor({
        'host': 'cluster.example.com',
        'username': 'researcher'
    })
    
    # Get detailed job information
    job_info = submitter.get_job_info(job_id)
    
    print(f"=== Job {job_id} Analysis ===")
    print(f"Status: {job_info.get('status', 'Unknown')}")
    print(f"Exit code: {job_info.get('exit_code', 'Unknown')}")
    print(f"Start time: {job_info.get('start_time', 'Unknown')}")
    print(f"End time: {job_info.get('end_time', 'Unknown')}")
    print(f"Elapsed time: {job_info.get('elapsed_time', 'Unknown')}")
    print(f"Node: {job_info.get('node', 'Unknown')}")
    
    # Check for common failure patterns
    if job_info.get('exit_code') == '125':
        print("ERROR: Job likely failed due to resource constraints")
    elif job_info.get('exit_code') == '1':
        print("ERROR: Job failed with general error")
    elif job_info.get('status') == 'TIMEOUT':
        print("ERROR: Job exceeded time limit")
    elif job_info.get('status') == 'OUT_OF_MEMORY':
        print("ERROR: Job ran out of memory")
    
    # Suggest debugging steps
    print("\n=== Debugging Suggestions ===")
    print("1. Check output files: debug_<job_id>.out and debug_<job_id>.err")
    print("2. Verify resource requirements (CPU, memory, time)")
    print("3. Check file permissions and paths")
    print("4. Validate module dependencies")
    print("5. Test script locally before submitting")

if __name__ == "__main__":
    # Submit debug job
    job_id = debug_job()
    print(f"Debug job submitted: {job_id}")
    
    # Wait for job to complete (in practice, you'd check periodically)
    input("Press Enter after job completes to analyze...")
    
    # Analyze the job
    analyze_failed_job(job_id)
```

## Integration with Hamilton

### Hamilton Dataflow with SLURM

```python title="hamilton_slurm.py"
from typing import Generator
import hamilton.driver
from molq import submit

# Configure SLURM cluster
hpc = submit('hpc', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'researcher',
    'partition': 'compute',
    'account': 'research_project'
})

# Hamilton functions with SLURM execution
@hpc
def data_ingestion(data_source: str) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'ingest_data.py', '--source', data_source],
        'job_name': 'data_ingestion',
        'cpus_per_task': 4,
        'memory': '16G',
        'time': '02:00:00',
        'output_file': 'ingestion_%j.out',
        'error_file': 'ingestion_%j.err',
        'block': True
    }
    return job_id

@hpc
def feature_engineering(ingestion_job_id: int) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'feature_engineering.py'],
        'job_name': 'feature_eng',
        'dependency': f'afterok:{ingestion_job_id}',
        'cpus_per_task': 8,
        'memory': '32G',
        'time': '04:00:00',
        'output_file': 'feature_eng_%j.out',
        'error_file': 'feature_eng_%j.err',
        'block': False
    }
    return job_id

@hpc
def model_training(feature_job_id: int) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'train_model.py', '--use-gpu'],
        'job_name': 'model_training',
        'dependency': f'afterok:{feature_job_id}',
        'gres': 'gpu:2',
        'cpus_per_task': 8,
        'memory': '64G',
        'time': '12:00:00',
        'partition': 'gpu',
        'output_file': 'training_%j.out',
        'error_file': 'training_%j.err',
        'block': False
    }
    return job_id

@hpc
def model_evaluation(training_job_id: int) -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'evaluate_model.py'],
        'job_name': 'model_eval',
        'dependency': f'afterok:{training_job_id}',
        'cpus_per_task': 4,
        'memory': '16G',
        'time': '01:00:00',
        'output_file': 'evaluation_%j.out',
        'error_file': 'evaluation_%j.err',
        'block': False
    }
    return job_id

def run_ml_workflow():
    """Run complete ML workflow using Hamilton + SLURM"""
    
    # Create Hamilton driver
    dr = hamilton.driver.Driver(
        {},
        data_ingestion,
        feature_engineering,
        model_training,
        model_evaluation
    )
    
    # Execute the workflow
    results = dr.execute(
        ['model_evaluation'],
        inputs={'data_source': '/data/training_data.csv'}
    )
    
    print(f"ML Workflow Results: {results}")
    return results

if __name__ == "__main__":
    results = run_ml_workflow()
```

## Best Practices

### Resource Optimization

```python title="resource_optimization.py"
from typing import Generator
from molq import submit

# Different cluster configurations for different job types
cpu_cluster = submit('cpu_jobs', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'researcher',
    'partition': 'cpu',
    'cpus_per_task': 16,
    'memory': '32G',
    'time': '04:00:00'
})

gpu_cluster = submit('gpu_jobs', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'researcher',
    'partition': 'gpu',
    'gres': 'gpu:2',
    'cpus_per_task': 8,
    'memory': '64G',
    'time': '12:00:00'
})

memory_cluster = submit('memory_jobs', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'researcher',
    'partition': 'highmem',
    'memory': '256G',
    'cpus_per_task': 32,
    'time': '24:00:00'
})

# Use appropriate cluster for each job type
@cpu_cluster
def cpu_intensive_task() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'cpu_task.py'],
        'job_name': 'cpu_task'
    }
    return job_id

@gpu_cluster
def gpu_intensive_task() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'gpu_task.py'],
        'job_name': 'gpu_task'
    }
    return job_id

@memory_cluster
def memory_intensive_task() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'memory_task.py'],
        'job_name': 'memory_task'
    }
    return job_id
```

### Error Recovery

```python title="error_recovery.py"
from typing import Generator
import time
from molq import submit

slurm = submit('robust_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'researcher',
    'partition': 'compute'
})

@slurm
def robust_job_with_retry() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': [
            'bash', '-c',
            '''
            # Retry logic built into the job script
            MAX_RETRIES=3
            RETRY_COUNT=0
            
            while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
                echo "Attempt $((RETRY_COUNT + 1)) of $MAX_RETRIES"
                
                if python fragile_script.py; then
                    echo "Job succeeded"
                    exit 0
                else
                    echo "Job failed, retrying in 60 seconds..."
                    sleep 60
                    RETRY_COUNT=$((RETRY_COUNT + 1))
                fi
            done
            
            echo "All retries failed"
            exit 1
            '''
        ],
        'job_name': 'robust_job',
        'cpus_per_task': 2,
        'memory': '8G',
        'time': '02:00:00',
        'output_file': 'robust_%j.out',
        'error_file': 'robust_%j.err',
        'block': False
    }
    return job_id

@slurm
def checkpointed_job() -> Generator[dict, int, int]:
    """Job with checkpointing for recovery"""
    job_id = yield {
        'cmd': [
            'python', 'checkpointed_computation.py',
            '--checkpoint-dir', '/scratch/$USER/checkpoints',
            '--resume-from-checkpoint'
        ],
        'job_name': 'checkpointed_job',
        'cpus_per_task': 8,
        'memory': '32G',
        'time': '24:00:00',
        'output_file': 'checkpoint_%j.out',
        'error_file': 'checkpoint_%j.err',
        'block': False
    }
    return job_id

if __name__ == "__main__":
    robust_job = robust_job_with_retry()
    checkpoint_job = checkpointed_job()
    
    print(f"Robust job: {robust_job}")
    print(f"Checkpointed job: {checkpoint_job}")
```

## Next Steps

- Learn about [Job Monitoring](monitoring.md) techniques
- Explore [Configuration](../user-guide/configuration.md) options
- Check [Local Jobs](local-jobs.md) for comparison
- Review [API Reference](../api/submitters.md) for all SLURM parameters
