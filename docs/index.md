# Molq

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Easy Integration**

    ---

    Seamlessly connect Hamilton workflows with job schedulers through simple decorators

    [:octicons-arrow-right-24: Getting started](getting-started/installation.md)

-   :material-server:{ .lg .middle } **Multiple Backends**

    ---

    Support for local execution and SLURM clusters with extensible architecture

    [:octicons-arrow-right-24: User Guide](user-guide/decorators.md)

-   :material-code-braces:{ .lg .middle } **Developer Friendly**

    ---

    Clean Python API with comprehensive examples and documentation

    [:octicons-arrow-right-24: Examples](examples/basic-usage.md)

-   :material-database:{ .lg .middle } **Job Management**

    ---

    Unified job tracking with SQLite database and rich CLI interface

    [:octicons-arrow-right-24: Job Management](user-guide/job-management.md)

</div>

## What is Molq?

**Molq** is a Python library that bridges [Hamilton](https://hamilton.dagworks.io) dataflows with job schedulers and execution environments. It provides decorators and tools to seamlessly submit, monitor, and manage computational jobs from your data pipelines.

### Key Features

- **Decorator-Based API**: Use `@submit` and `@cmdline` decorators to execute jobs seamlessly
- **Multiple Execution Backends**: Support for local processes and SLURM clusters
- **Unified Job Management**: SQLite-based job database with automatic status tracking
- **Rich CLI Interface**: Command-line tools for job submission, monitoring, and management
- **Hamilton Integration**: Purpose-built for Hamilton dataflow orchestration
- **Extensible Architecture**: Easy to add support for new schedulers and environments
- **Resource Management**: Flexible resource specification and configuration

## Quick Example

```python title="Basic Job Submission"
from molq import submit
from molq.resources import BaseResourceSpec

# Create a local submitter
local = submit('my_project', 'local')

@local
def run_analysis():
    """Submit a data analysis job."""
    spec = BaseResourceSpec(
        cmd=['python', 'analyze_data.py', '--input', 'data.csv'],
        job_name='data-analysis',
        cpu_count=4,
        memory='8GB'
    )
    job_id = yield spec.model_dump()
    return job_id

# Submit and get job ID
job_id = run_analysis()
print(f"Job submitted with ID: {job_id}")
```

```bash title="CLI Job Management"
# List all active jobs
molq list

# Check specific job status
molq status 12345

# Cancel a running job
molq cancel 12345

# Submit job via CLI
molq submit --scheduler local --cmd "echo hello" --job-name test
```

!!! tip "Ready to get started?"
    
    Check out the [installation guide](getting-started/installation.md) to begin using Molq in your projects.

## Community & Support

- **GitHub**: [roykid/molq](https://github.com/roykid/molq) - Source code and issue tracking
- **PyPI**: [molq](https://pypi.org/project/molq/) - Package distribution
- **Documentation**: Comprehensive guides and API reference
