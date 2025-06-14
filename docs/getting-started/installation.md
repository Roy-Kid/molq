# Installation

## Requirements

Molq requires Python 3.9 or higher and has the following dependencies:

- **Hamilton** (`sf-hamilton`) - The core dataflow framework
- **Paramiko** - For SSH connections to remote clusters

## Install from PyPI

The easiest way to install Molq is using pip:

```bash
pip install molq
```

## Install from Source

If you want to install the latest development version:

```bash
git clone https://github.com/roykid/molq.git
cd molq
pip install -e .
```

## Development Installation

For contributing to Molq, install with development dependencies:

```bash
git clone https://github.com/roykid/molq.git
cd molq
pip install -e ".[dev]"
```

This includes additional packages for testing and development:

- `pytest` - Testing framework
- `pytest-mock` - Mocking utilities for tests
- `coverage` - Code coverage analysis
- `build` - Package building tools

## Verify Installation

You can verify that Molq is installed correctly by running:

```python
import molq
print(molq.__version__)
```

Or run a simple test:

```python
from molq import cmdline

@cmdline
def test_installation() -> str:
    cp = yield {"cmd": "echo 'Molq is working!'", "block": True}
    return cp.stdout.decode().strip()

if __name__ == "__main__":
    print(test_installation())
```

## Next Steps

Now that you have Molq installed, you can:

- Follow the [Quick Start Guide](quick-start.md) to run your first job
- Learn about [Basic Concepts](concepts.md) behind Molq
- Explore the [Examples](../examples/cmdline.md) for common use cases
