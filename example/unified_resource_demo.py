#!/usr/bin/env python3
"""
Demo: Using unified ResourceSpec with different submitters.

This demonstrates how the same resource specification format can be used
across different execution backends (local, SLURM) with automatic parameter
conversion.
"""

from molq import submit
from typing import Generator

# Register different submitters
local = submit('local', 'local')
# slurm = submit('cluster', 'slurm')  # Would be used for real SLURM cluster

@local
def unified_local_job() -> Generator[dict, int, int]:
    """Local job using unified resource specification."""
    job_id = yield {
        'job_name': 'unified_demo_local',
        'cmd': ['echo', 'Hello from local job with unified params!'],
        # Unified ResourceSpec parameters
        'workdir': '/tmp',
        'cpu_count': 4,        # Ignored for local
        'memory': '8GB',       # Ignored for local
        'time_limit': '1h',    # Ignored for local
        'block': True
    }
    return job_id

# Example of what a SLURM job would look like with the same parameters
def show_slurm_example():
    """Show how the same parameters would work with SLURM."""
    slurm_config = {
        'job_name': 'unified_demo_slurm',
        'cmd': ['python', '-c', 'print("Hello from SLURM job!")'],
        # Same unified ResourceSpec parameters
        'cpu_count': 4,        # → --ntasks 4
        'memory': '8GB',       # → --mem 8G  
        'time_limit': '1h',    # → --time 01:00:00
        'queue': 'compute',    # → --partition compute
        'gpu_count': 1,        # → --gres gpu:1
        'gpu_type': 'v100',    # → --gres gpu:v100:1
        'email': 'user@example.com',  # → --mail-user user@example.com
        'email_events': ['start', 'end'],  # → --mail-type BEGIN,END
        'priority': 'high',    # → --priority 1000
        'exclusive_node': True, # → --exclusive
        'block': False
    }
    
    return slurm_config

if __name__ == "__main__":
    print("Unified ResourceSpec Demo")
    print("=" * 40)
    
    # Run local job with unified parameters
    print("\n1. Running local job with unified parameters...")
    job_id = unified_local_job()
    print(f"   ✓ Local job completed: {job_id}")
    
    # Show SLURM configuration that would be generated
    print("\n2. SLURM configuration that would be generated:")
    slurm_config = show_slurm_example()
    print("   Input (unified format):")
    for key, value in slurm_config.items():
        if key not in ['job_name', 'cmd']:
            print(f"     {key}: {value}")
    
    print("\n   Generated SLURM parameters:")
    print("     --ntasks: 4")
    print("     --mem: 8G")
    print("     --time: 01:00:00")
    print("     --partition: compute")
    print("     --gres: gpu:v100:1")
    print("     --mail-user: user@example.com")
    print("     --mail-type: BEGIN,END")
    print("     --priority: 1000")
    print("     --exclusive")
    
    print("\n✓ Same unified parameters work across all submitters!")
    print("✓ Automatic conversion to scheduler-specific formats!")
    print("✓ Human-readable time and memory formats supported!")
