# API Documentation

Welcome to the Molq API Reference! This documentation is automatically generated from the Python source code using `mkdocstrings`.

## Overview

The API documentation is organized into the following sections:

### [Core Functions](core.md)
Core decorators and utility functions for job submission:
- `submit` - Primary decorator for creating job submitters  
- `cmdline` - Simplified decorator for command-line execution
- `YieldDecorator` - Base class for generator-based decorators

### [Decorators](decorators.md) 
Detailed documentation for all decorators:
- Usage patterns and examples
- Function signatures and parameters
- Return values and behavior

### [Submitters](submitters.md)
Job submitter classes and their methods:
- `BaseSubmitor` - Abstract base class
- `LocalSubmitor` - Local job execution
- `SlurmSubmitor` - SLURM cluster integration
- `JobStatus` - Job status tracking

### [Resources](resources.md)
Resource specification system:
- `BaseResourceSpec` - Basic resource requirements
- `ComputeResourceSpec` - CPU/memory specifications  
- `ClusterResourceSpec` - Advanced cluster features
- Utility functions and parsers

### [CLI](cli.md)
Command-line interface:
- CLI commands and options
- Configuration management
- Utility functions

## Features

- **Auto-Generated**: Documentation is extracted directly from docstrings
- **Type Information**: Shows parameter types and return values
- **Categorized**: Methods grouped by functionality  
- **Examples**: Code examples where available
- **Cross-References**: Links between related functions

## Usage Patterns

The API follows these general patterns:

```python
# Decorator pattern for job submission
from molq import submit

local = submit('project', 'local')

@local  
def my_job():
    spec = {'cmd': ['echo', 'hello'], 'job_name': 'test'}
    job_id = yield spec
    return job_id

# Direct submitter usage
from molq import LocalSubmitor

submitter = LocalSubmitor()
job_id = submitter.local_submit('test', ['echo', 'hello'])
```

For detailed examples and usage instructions, see the [User Guide](../user-guide/decorators.md) and [Examples](../examples/basic-usage.md) sections.
