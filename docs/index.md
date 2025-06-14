# Molq Documentation

Molq helps you integrate [Hamilton](https://hamilton.dagworks.io) workflows with traditional job schedulers. Jobs can run locally or be dispatched to clusters through a simple decorator based API.

## Installation

```bash
pip install molq
```

## Quick Start

Register a submitter for the current machine and run a command:

```python
from molq import submit, cmdline

local = submit('local', 'local')

@local
def my_job() -> int:
    job_id = yield {
        'cmd': ['echo', 'hi'],
        'job_name': 'demo',
        'block': True,
    }
    return job_id
```

The `cmdline` decorator executes shell commands inside a node:

```python
@cmdline
def echo() -> str:
    cp = yield {'cmd': 'echo hello', 'block': True}
    return cp.stdout.decode().strip()
```

## API Overview

- **submit** – register clusters and submit jobs to them.
- **cmdline** – run shell commands within generator nodes.
- **LocalSubmitor** – executes jobs on the local machine.
- **SlurmSubmitor** – submits jobs to a SLURM cluster.

See the examples directory for more usage patterns.
