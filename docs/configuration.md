# Durable configuration

SQLite contains exactly schema_meta, clusters, settings and presets. It stores registry identity/schema, explicit destination definitions, Runtime settings and submission presets. Job states/history/events/leases/retries are absent.

Default registry: MOLQ_REGISTRY, otherwise LOCALAPPDATA/molq/registry.db on Windows or XDG_STATE_HOME/molq/registry.db (default ~/.local/state) on POSIX. --registry selects another path without touching old jobs.db. Importing molq creates nothing.

Cluster updates/removal require expected_revision. Name changes preserve ID. Scheduler, Transport and target_root changes require registering a new Cluster; saved references cannot silently retarget native jobs. Removing a Cluster never cancels native jobs, but its configuration must be restored to access them.

config.get/set keys: cache_max_entries (bounded cache size), cache_max_age (default bounded-query freshness), default_cluster (saved preference; explicit scopes remain required by RPC). presets.list/get/set stores Defaults values; select and pass preset fields explicitly. Startup reloads cache settings; no Job snapshots survive.

One registry normally has one active Runtime. SQLite uses short WAL transactions with bounded STATE_BUSY and revision conflicts for accidental overlap. Transactions never encompass scheduler/SSH operations. Do not share the registry through NFS or expect cache/cursor/event synchronization across Runtime processes.

Credentials, cadence and notification routes are client/deployment configuration. SSH connection details belong to OpenSSH.
