# Molq

**Molq** is a small helper library that connects [Hamilton](https://hamilton.dagworks.io) with local or cluster based job runners. It provides a couple of decorators so you can launch jobs or run shell commands straight from your dataflow code.

## Installation

```
pip install molq
```

## Quick Example

```python
from molq import submit, cmdline

# Register the local machine as a cluster
local = submit('local', 'local')

@local
def run_job() -> int:
    job_id = yield {
        'cmd': ['echo', 'hello'],
        'job_name': 'demo',
        'block': True,
    }
    return job_id

@cmdline
def echo_node() -> str:
    cp = yield {'cmd': 'echo world', 'block': True}
    return cp.stdout.decode().strip()
```

See the [documentation](docs/index.md) for a more complete tour and additional examples.
