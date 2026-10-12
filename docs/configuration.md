# Durable configuration

SQLite schema 2 contains exactly `schema_meta` and `clusters`: registry identity,
schema version, and explicit destination definitions. Job states, history,
events, leases and retries are absent.

The default file is `~/.molcrafts/molq/config.json`. `--config` selects another
`.json`, `.yaml` or `.yml` file. When `--config` is omitted and the default
file exists, the CLI loads it. A missing default leaves the configuration
empty. An unreadable or invalid file is an error. Files are never combined.
Importing molq creates no configuration directories or files. Connection
settings are not read from the environment.

```json
{
  "settings": {"cache_max_entries": 4096, "cache_max_age": 5},
  "presets": {"small": {"resources": {"tasks": 1}}}
}
```

Registry selection is `--registry`, `client.registry`, or
`~/.molcrafts/molq/registry.db`. Configuration and the registry live in the same
directory.

`config.get/set` manages `cache_max_entries`, `cache_max_age`, and
`default_cluster` (saved preference; RPC scopes remain explicit).
`presets.list/get/set` manages validated Defaults values; clients select and pass
preset fields explicitly. These methods use the Runtime's configuration file,
not the client's filesystem. Startup validates the whole file; `config.reload`
loads external edits and invalidates disposable observations. Invalid reloads
preserve the previous configuration. Reload applies cache settings and resets
observation cursors. Credentials, cadence and notification routes remain
client/deployment configuration. SSH connection details belong to OpenSSH.

RPC writes lock the file, re-read it, validate all namespaces, and replace it
atomically using a flushed temporary file in the same directory. Lock contention
is bounded and returns `STATE_BUSY`. Other Runtime instances must explicitly
reload; file writes do not create a multi-Runtime synchronization service.

## Registry file

1.0 is the first registry layout. There is no older API schema to migrate.
A database that is not `schema_meta` plus `clusters` at the current schema
marker is rejected with `STATE_SCHEMA_INCOMPATIBLE` and left unchanged.

Cluster updates/removal require `expected_revision`; rename preserves identity.
Scheduler, Transport and target_root changes require a new Cluster. Removing
configuration never cancels jobs, but restore the definition to access them.
One registry normally has one active Runtime. SQLite uses short WAL transactions;
no transaction encompasses SSH/scheduler operations. Use local disk, not shared
NFS, and do not expect cross-process observation synchronization.
