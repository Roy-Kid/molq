# Plugins and Nerve

Plugins observe a `Submitor` session without receiving scheduler or store write
access. They can subscribe to lifecycle events and read records through a
narrow `PluginContext`.

## List available plugins

```bash
molq plugins list
```

molq discovers:

- official plugins bundled in `molq.plugins`;
- third-party packages registered in the `molq.plugins` entry-point group.

Official names take precedence if a third-party package declares the same
entry-point name.

## Attach a plugin in Python

```python
import molq as mq

cluster = mq.Cluster("laptop", "local")

with mq.Submitor(
    target=cluster,
    plugins=["nerve"],
    plugin_configs={
        "nerve": {
            "expand_threshold": 8,
            "show_members": "attention",
        }
    },
) as queue:
    job = queue.submit_job(argv=["python", "analyse.py"])
    job.wait()
```

Plugins attach for the lifetime of the `Submitor` and detach during `close()`.
Attachment failures are logged and skipped so an observability plugin cannot
block job submission.

## Configure plugins

Put plugin settings at the top level of the molq config file:

```yaml
plugins:
  nerve:
    enabled: true
    expand_threshold: 8
    debounce_seconds: 0.3
    ingest_url: "http://127.0.0.1:17890"
    show_members: attention
```

`show_members` accepts `never`, `attention`, or `all`.

Explicit `plugins` entries control which plugins the CLI loads. Set
`enabled: false` to disable one:

```yaml
plugins:
  nerve:
    enabled: false
```

## Nerve integration

The official `nerve` plugin sends roll-up job snapshots to the local Nerve hub:

```text
http://127.0.0.1:17890/v1/snapshot
```

It is display-only and fail-open. If Nerve is not running, submission and
monitoring continue normally.

`molq daemon` enables Nerve by default only when the config has no
`[plugins]` entries:

```bash
molq daemon slurm --cluster dardel
```

As soon as any plugin table exists, the config becomes authoritative.

## Third-party plugin contract

A plugin factory returns an object with:

```python
class MyPlugin:
    name = "my_plugin"

    def attach(self, ctx):
        ctx.event_bus.on(mq.EventType.STATUS_CHANGE, self.on_status)

    def detach(self):
        ...
```

Register the zero-argument factory in package metadata:

```toml
[project.entry-points."molq.plugins"]
my_plugin = "my_package.plugin:create_plugin"
```

`PluginContext` exposes the event bus, cluster name, plugin config, and
read-only record accessors. Plugins should keep event handlers non-blocking and
must not reach into scheduler or store internals.
