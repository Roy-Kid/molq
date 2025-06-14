# Molcrafts Orchestrator

Molq provides decorators and submitter classes so that
[Hamilton](https://hamilton.dagworks.io) workflows can easily run
on local machines or SLURM clusters. Jobs are launched by a
``submit`` decorator while shell commands inside nodes can be
executed through ``cmdline``.

## Features

- Register multiple clusters and dispatch jobs to them.
- Monitor running jobs from Python.
- Lightweight local execution for simple workflows.

See the README for a quick start.
