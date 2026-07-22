---
title: molq
description: Unified job queue for local execution and HPC schedulers.
hide:
  - navigation
  - toc
hero:
  title: molq
  description: One submission interface for local runs and HPC queues. Pair a <code>Cluster</code> (where) with a <code>Submitor</code> (lifecycle), track jobs in SQLite, and watch them from the CLI or the menu bar.
  install:
    label: Install
    command: pip install molcrafts-molq
  badges:
    - img: https://img.shields.io/pypi/v/molcrafts-molq
      href: https://pypi.org/project/molcrafts-molq/
      alt: PyPI version
    - img: https://img.shields.io/badge/python-3.12%2B-blue.svg
      href: https://pypi.org/project/molcrafts-molq/
      alt: Python 3.12+
    - img: https://img.shields.io/badge/license-MIT-blue.svg
      href: https://github.com/MolCrafts/molq/blob/master/LICENSE
      alt: License MIT
  actions:
    - label: Get started
      href: getting-started/
      style: primary
    - label: Concepts
      href: concepts/
    - label: API reference
      href: api/
---

<h1 class="molcrafts-sr-only">molq</h1>

<div class="molcrafts-manual-home" markdown>

<!-- ────────────────────────────────────────────────────────────
     AT A GLANCE — compact frame: static label + one code block
     ──────────────────────────────────────────────────────────── -->

<section class="molcrafts-manual-section molcrafts-manual-section--compact" markdown>

<div class="molcrafts-manual-section__header" markdown>

<span class="molcrafts-manual-eyebrow">At a glance</span>

## Cluster × Submitor, same code local or remote

`Cluster` is the destination (scheduler + transport). `Submitor` owns
lifecycle, SQLite, and events. Swap `"local"` for `"slurm"` and pass
`host=` for SSH — no other code changes.

</div>

```python
import molq as mq

cluster  = mq.Cluster("hpc", "slurm", host="user@hpc.example.com")
submitor = mq.Submitor(target=cluster)

handle = submitor.submit_job(
    argv=["python", "train.py"],
    resources=mq.JobResources(
        cpu_count=8,
        memory=mq.Memory.gb(32),
        time_limit=mq.Duration.hours(4),
    ),
    scheduling=mq.JobScheduling(partition="gpu"),
)
record = handle.wait()
print(record.state, cluster.get_queue())
```

</section>

<!-- ────────────────────────────────────────────────────────────
     CAPABILITIES — stack frame + 2-column grid of linked cards
     ──────────────────────────────────────────────────────────── -->

<section class="molcrafts-manual-section molcrafts-manual-section--stack" markdown>

<div class="molcrafts-manual-section__header" markdown>

<span class="molcrafts-manual-eyebrow">What molq gives you</span>

## One queue model, several backends

</div>

<div class="molcrafts-manual-grid molcrafts-manual-grid--cols-2">
  <a href="concepts/">
    <strong>Two-axis design</strong>
    <p><code>Cluster</code> (where) × <code>Submitor</code> (lifecycle). Scheduler × Transport are independent — local SLURM or remote shell via SSH.</p>
  </a>
  <a href="schedulers/">
    <strong>local · SLURM · PBS · LSF</strong>
    <p>Typed resources and options instead of hand-built <code>sbatch</code> strings. Live queue snapshots with <code>cluster.get_queue()</code>.</p>
  </a>
  <a href="monitoring/">
    <strong>Durable monitoring</strong>
    <p>SQLite WAL store, reconciliation, retries, dependencies, and a Rich full-screen dashboard.</p>
  </a>
  <a href="cli/">
    <strong>CLI &amp; plugins</strong>
    <p>Submit, watch, inspect, daemon. Official Nerve plugin ships with molq for menu-bar job status.</p>
  </a>
  <a href="getting-started/">
    <strong>SSH for free</strong>
    <p>Uses system <code>ssh</code>/<code>rsync</code> and your <code>~/.ssh/config</code> — ProxyJump, ControlMaster, agent, Kerberos.</p>
  </a>
  <a href="api/">
    <strong>Frozen public types</strong>
    <p>Immutable dataclasses for resources, records, and events. Zero import side effects.</p>
  </a>
</div>

</section>

<!-- ────────────────────────────────────────────────────────────
     MANUAL INDEX — stack frame, full-width numbered chapter list
     ──────────────────────────────────────────────────────────── -->

<section class="molcrafts-manual-section molcrafts-manual-section--stack" markdown>

<div class="molcrafts-manual-section__header" markdown>

<span class="molcrafts-manual-eyebrow">Find your page</span>

## The manual

</div>

<nav class="molcrafts-manual-index" aria-label="Manual chapters">
  <a href="getting-started/">
    <span>01</span>
    <strong>Getting Started</strong>
    <em>Install molq, open a Cluster + Submitor, submit the first job.</em>
  </a>
  <a href="concepts/">
    <span>02</span>
    <strong>Concepts</strong>
    <em>Cluster, Submitor, Scheduler, Transport, Workspace, plugins.</em>
  </a>
  <a href="schedulers/">
    <span>03</span>
    <strong>Schedulers</strong>
    <em>Backend matrix and scheduler option classes.</em>
  </a>
  <a href="monitoring/">
    <span>04</span>
    <strong>Monitoring</strong>
    <em>Lifecycle, reconciliation, polling, dashboards, and logs.</em>
  </a>
  <a href="cli/">
    <span>05</span>
    <strong>CLI</strong>
    <em>Command groups: jobs, history, live, setup (clusters, workspace, plugins).</em>
  </a>
  <a href="api/">
    <span>06</span>
    <strong>API Reference</strong>
    <em>Exported classes, enums, options, plugins, and errors.</em>
  </a>
  <a href="release-notes/">
    <span>07</span>
    <strong>Changelog</strong>
    <em>Release series notes.</em>
  </a>
</nav>

</section>

</div>
