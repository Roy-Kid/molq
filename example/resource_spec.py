#!/usr/bin/env python3
"""
Example: Using the new layered resource specification system
"""

from pathlib import Path
import sys

# Add project path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from molq.resources import (
    BaseResourceSpec, 
    ComputeResourceSpec, 
    ClusterResourceSpec,
    ResourceManager,
    create_compute_job,
    create_gpu_job,
    create_array_job,
    create_high_memory_job,
    PriorityLevel,
    EmailEvent
)


def demo_base_resource_spec():
    """Demonstrate base resource specification (suitable for local execution)"""
    print("=== Base Resource Spec Demo ===")
    
    # Base resource specification, suitable for local execution
    base_spec = BaseResourceSpec(
        cmd=["python", "train.py"],
        workdir="/tmp/workspace",
        env={"CUDA_VISIBLE_DEVICES": "0"},
        job_name="local_training",
        output_file="output.log",
        error_file="error.log"
    )
    
    print(f"Command: {base_spec.cmd}")
    print(f"Working directory: {base_spec.workdir}")
    print(f"Environment: {base_spec.env}")
    print(f"Job name: {base_spec.job_name}")
    print()


def demo_compute_resource_spec():
    """Demonstrate compute resource specification"""
    print("=== Compute Resource Spec Demo ===")
    
    # Compute resource specification, including CPU, memory, time limits
    compute_spec = ComputeResourceSpec(
        cmd="python train.py --epochs 100",
        cpu_count=8,
        memory="16GB",
        time_limit="4h30m",
        job_name="compute_training",
        workdir="/home/user/project"
    )
    
    print(f"Command: {compute_spec.cmd}")
    print(f"CPU cores: {compute_spec.cpu_count}")
    print(f"Memory: {compute_spec.memory}")
    print(f"Time limit: {compute_spec.time_limit}")
    print()


def demo_cluster_resource_spec():
    """Demonstrate cluster resource specification"""
    print("=== Cluster Resource Spec Demo ===")
    
    # Cluster resource specification, including all advanced features
    cluster_spec = ClusterResourceSpec(
        cmd=["python", "distributed_train.py", "--nodes", "2"],
        queue="gpu",
        node_count=2,
        cpu_per_node=16,
        memory="64GB",
        memory_per_cpu="4GB",
        gpu_count=4,
        gpu_type="v100",
        time_limit="12h",
        priority=PriorityLevel.HIGH,
        job_name="distributed_training",
        email="user@example.com",
        email_events=[EmailEvent.START, EmailEvent.END, EmailEvent.FAIL],
        account="research_group",
        qos="high_priority",
        exclusive_node=True,
        constraints=["intel", "infiniband"],
        comment="Large scale distributed training job"
    )
    
    print(f"Command: {cluster_spec.cmd}")
    print(f"Queue: {cluster_spec.queue}")
    print(f"Nodes: {cluster_spec.node_count}")
    print(f"CPUs per node: {cluster_spec.cpu_per_node}")
    print(f"GPUs: {cluster_spec.gpu_count} x {cluster_spec.gpu_type}")
    print(f"Memory: {cluster_spec.memory}")
    print(f"Priority: {cluster_spec.priority}")
    print(f"Email: {cluster_spec.email}")
    print(f"Email events: {cluster_spec.email_events}")
    print()


def demo_convenience_functions():
    """Demonstrate convenience functions"""
    print("=== Convenience Functions Demo ===")
    
    # Create compute job
    compute_job = create_compute_job(
        cmd="python analysis.py",
        cpu_count=4,
        memory="8GB",
        time_limit="2h",
        queue="compute"
    )
    print(f"Compute job: {compute_job.queue}, {compute_job.cpu_count} CPUs, {compute_job.memory}")
    
    # Create GPU job
    gpu_job = create_gpu_job(
        cmd="python gpu_train.py",
        gpu_count=2,
        gpu_type="a100",
        cpu_count=8,
        memory="32GB",
        time_limit="8h"
    )
    print(f"GPU job: {gpu_job.gpu_count} x {gpu_job.gpu_type}, {gpu_job.cpu_count} CPUs")
    
    # Create array job
    array_job = create_array_job(
        cmd="python batch_process.py --task $SLURM_ARRAY_TASK_ID",
        array_spec="1-100:5",
        cpu_count=1,
        memory="2GB",
        time_limit="30m"
    )
    print(f"Array job: {array_job.array_spec}, {array_job.cpu_count} CPU per task")
    
    # Create high memory job
    highmem_job = create_high_memory_job(
        cmd="python big_data_analysis.py",
        memory="256GB",
        cpu_count=32,
        time_limit="24h"
    )
    print(f"High memory job: {highmem_job.memory}, exclusive: {highmem_job.exclusive_node}")
    print()


def demo_scheduler_mapping():
    """Demonstrate scheduler mapping"""
    print("=== Scheduler Mapping Demo ===")
    
    # Create a sample specification
    spec = ClusterResourceSpec(
        cmd="python example.py",
        queue="gpu",
        cpu_count=8,
        memory="16GB",
        time_limit="2h30m",
        gpu_count=1,
        gpu_type="v100",
        job_name="test_job",
        email="user@example.com",
        email_events=[EmailEvent.END]
    )
    
    # Map to different schedulers
    schedulers = ["slurm", "pbs", "lsf"]
    
    for scheduler in schedulers:
        print(f"\n--- {scheduler.upper()} Mapping ---")
        try:
            mapped_params = ResourceManager.map_to_scheduler(spec, scheduler)
            for param, value in mapped_params.items():
                print(f"  {param}: {value}")
            
            # Generate command line arguments
            command_args = ResourceManager.format_command_args(spec, scheduler)
            print(f"  Command args: {' '.join(command_args)}")
        except Exception as e:
            print(f"  Error: {e}")


def demo_validation():
    """Demonstrate parameter validation"""
    print("=== Validation Demo ===")
    
    try:
        # Test time format validation
        valid_spec = ComputeResourceSpec(
            cmd="test",
            time_limit="2h30m",
            memory="8GB"
        )
        print("✓ Valid time and memory formats accepted")
        
        # Test invalid time format
        try:
            invalid_spec = ComputeResourceSpec(
                cmd="test",
                time_limit="invalid_time"
            )
        except ValueError as e:
            print(f"✓ Invalid time format rejected: {e}")
        
        # Test GPU consistency validation
        try:
            invalid_gpu_spec = ClusterResourceSpec(
                cmd="test",
                gpu_type="v100"  # Specified GPU type but no count
            )
        except ValueError as e:
            print(f"✓ GPU consistency validation: {e}")
        
        # Test CPU consistency validation
        try:
            invalid_cpu_spec = ClusterResourceSpec(
                cmd="test",
                cpu_count=16,
                cpu_per_node=8,
                node_count=3  # 8*3=24 != 16
            )
        except ValueError as e:
            print(f"✓ CPU consistency validation: {e}")
            
    except Exception as e:
        print(f"Validation error: {e}")
    
    print()


def main():
    """Main function to run all demonstrations"""
    print("Molq Resource Specification System Demo")
    print("=" * 50)
    print()
    
    demo_base_resource_spec()
    demo_compute_resource_spec()
    demo_cluster_resource_spec()
    demo_convenience_functions()
    demo_scheduler_mapping()
    demo_validation()
    
    print("Demo completed successfully!")


if __name__ == "__main__":
    main()
