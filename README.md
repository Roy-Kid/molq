# Molq: Hamilton Job Orchestrator

Molq is a lightweight library that integrates the
[Hamilton](https://hamilton.dagworks.io) workflow engine with
traditional HPC schedulers. It exposes a ``submit`` decorator to
register clusters and send jobs and a ``cmdline`` decorator for
running shell commands inside nodes.

```bash
pip install -e .
```

## Usage

```python
from molq import submit, cmdline

# register a local cluster
local = submit('local', 'local')

@local
def run_job() -> int:
    job = yield {
        'cmd': ['echo', 'hi'],
        'job_name': 'demo',
    }
    return job

@cmdline
def echo_node() -> str:
    cp = yield {'cmd': 'echo hello', 'block': True}
    return cp.stdout.decode().strip()
```

See ``docs/index.md`` for more details.
