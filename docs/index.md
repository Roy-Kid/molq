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

    [:octicons-arrow-right-24: Examples](examples/cmdline.md)

-   :material-cog:{ .lg .middle } **Flexible Configuration**

    ---

    Configurable job parameters and execution environments

    [:octicons-arrow-right-24: Configuration](user-guide/configuration.md)

</div>

## What is Molq?

**Molq** is a small helper library that connects [Hamilton](https://hamilton.dagworks.io) with local or cluster-based job runners. It provides a couple of decorators so you can launch jobs or run shell commands straight from your dataflow code.

### Key Features

- **Simple Decorators**: Use `@submit` and `@cmdline` decorators to execute jobs
- **Multiple Backends**: Support for local execution and SLURM clusters
- **Generator-Based**: Leverage Python generators for flexible job control
- **Hamilton Integration**: Designed specifically for Hamilton workflows
- **Extensible**: Easy to add support for new job schedulers

## Quick Example

```python title="Basic Usage"
from typing import Generator
import subprocess
from molq import submit, cmdline

# Register the local machine as a cluster
local = submit('local', 'local')

@local
def run_job() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['echo', 'hello'],
        'job_name': 'demo',
        'block': True,
    }
    return job_id

@cmdline
def echo_node() -> Generator[dict, subprocess.CompletedProcess, str]:
    cp = yield {'cmd': 'echo world', 'block': True}
    return cp.stdout.decode().strip()
```

!!! tip "Ready to get started?"
    
    Check out the [installation guide](getting-started/installation.md) to begin using Molq in your projects.

## Community & Support

- **GitHub**: [roykid/molq](https://github.com/roykid/molq) - Source code and issue tracking
- **PyPI**: [molq](https://pypi.org/project/molq/) - Package distribution
- **Documentation**: Comprehensive guides and API reference
