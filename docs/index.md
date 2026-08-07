---
title: molq
description: One Python interface for local commands and HPC schedulers.
hide:
  - navigation
  - toc
hero:
  kicker: Job orchestration
  title: molq
  description: Submit, track, and inspect the same workload on your laptop or an HPC cluster. molq keeps scheduler details at the edge and job history in one durable queue.
  actions:
    - label: Run your first job
      href: getting-started/
      style: primary
    - label: Connect a cluster
      href: schedulers/
    - label: Python API
      href: api/
  install:
    label: Install
    methods:
      - label: pip
        command: pip install molcrafts-molq
      - label: uv
        command: uv add molcrafts-molq
  badges:
    - img: https://img.shields.io/pypi/v/molcrafts-molq
      href: https://pypi.org/project/molcrafts-molq/
      alt: PyPI version
    - img: https://img.shields.io/pypi/pyversions/molcrafts-molq
      href: https://pypi.org/project/molcrafts-molq/
      alt: Supported Python versions
    - img: https://img.shields.io/badge/license-MIT-18432B
      href: https://github.com/MolCrafts/molq/blob/master/LICENSE
      alt: MIT license
---

<h1 class="molcrafts-sr-only">molq documentation</h1>

<div class="molcrafts-manual-home" markdown>

<section class="molcrafts-manual-section molcrafts-manual-section--compact" markdown>

<div class="molcrafts-manual-section__header" markdown>

<span class="molcrafts-manual-eyebrow">Start local</span>

## One queue, seven lines

Begin with a real local process. The same `submit_job()` and `wait()` calls
work when the destination becomes SLURM, PBS, or LSF.

</div>

```python
import molq as mq

cluster = mq.Cluster("laptop", "local")
with mq.Submitor(target=cluster) as queue:
    job = queue.submit_job(
        argv=["python", "-c", "print('hello from molq')"]
    )
    result = job.wait()

print(result.state.value)
```

</section>

<section class="molcrafts-manual-section molcrafts-manual-section--stack" markdown>

<div class="molcrafts-manual-section__header" markdown>

<span class="molcrafts-manual-eyebrow">Choose a path</span>

## Find the page you need

</div>

<nav class="molcrafts-manual-index" aria-label="Documentation entry points">
  <a href="getting-started/">
    <span>01</span>
    <strong>Run a first job</strong>
    <em>Install molq, execute a local command, and inspect the result.</em>
  </a>
  <a href="jobs/">
    <span>02</span>
    <strong>Describe a real workload</strong>
    <em>Add resources, working directories, retries, and dependencies.</em>
  </a>
  <a href="schedulers/">
    <span>03</span>
    <strong>Connect an HPC cluster</strong>
    <em>Choose a scheduler and run it locally or through an SSH alias.</em>
  </a>
  <a href="monitoring/">
    <span>04</span>
    <strong>Inspect running work</strong>
    <em>Understand persisted state, live queues, logs, and dashboards.</em>
  </a>
</nav>

</section>

<section class="molcrafts-manual-section" markdown>

<div class="molcrafts-manual-section__header" markdown>

<span class="molcrafts-manual-eyebrow">Mental model</span>

## Four objects are enough

`Cluster` describes a destination. `Submitor` owns submission and tracking.
`JobHandle` follows one submitted job. `JobRecord` is an immutable snapshot
you can store, print, or return from a service.

</div>

<dl class="molcrafts-feature-matrix">
  <div>
    <dt>Cluster</dt>
    <dd>Scheduler plus transport: what queue system to use and where its commands execute.</dd>
  </div>
  <div>
    <dt>Submitor</dt>
    <dd>The lifecycle boundary: submission, SQLite history, reconciliation, retries, and events.</dd>
  </div>
  <div>
    <dt>JobHandle</dt>
    <dd>The live convenience object returned by submission: status, refresh, wait, and cancel.</dd>
  </div>
  <div>
    <dt>JobRecord</dt>
    <dd>A frozen view of state, timestamps, exit status, command metadata, and artifact paths.</dd>
  </div>
</dl>

</section>

<section class="molcrafts-manual-section molcrafts-manual-section--stack" markdown>

<div class="molcrafts-manual-section__header" markdown>

<span class="molcrafts-manual-eyebrow">Backends</span>

## Change the destination, keep the workflow

</div>

<div class="molcrafts-manual-grid molcrafts-manual-grid--cols-2">
  <a href="schedulers/#common-destinations">
    <strong>Local</strong>
    <em>Run ordinary processes on this machine or a remote workstation.</em>
  </a>
  <a href="schedulers/#slurm">
    <strong>SLURM</strong>
    <em>Submit with sbatch and reconcile with squeue and sacct.</em>
  </a>
  <a href="schedulers/#pbs">
    <strong>PBS / Torque</strong>
    <em>Translate the same typed request into qsub options.</em>
  </a>
  <a href="schedulers/#lsf">
    <strong>LSF</strong>
    <em>Submit and monitor through bsub, bjobs, bkill, and bhist.</em>
  </a>
</div>

</section>

</div>
