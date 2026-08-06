# Release notes

Curated highlights per release. Complete history is git tags / GitHub Releases
(no hand-written `CHANGELOG.md`).

## 0.6.0

Released 2026-07-22.

### Plugin host

- Added the `MolqPlugin` protocol, read-only `PluginContext`, and
  `PluginManager`.
- Official plugins ship with molq; third-party plugins load from the
  `molq.plugins` entry-point group.
- `Submitor` accepts `plugins=` and `plugin_configs=`.
- The official Nerve plugin sends fail-open status rollups to the local Nerve
  menu-bar app.
- Added `molq plugins list`; `molq daemon` defaults to Nerve when no plugin
  table is configured.

### Documentation

- Adopted the packaged MolCrafts Zensical theme.
- Reorganized the manual around runnable tutorials, task guides, and generated
  API reference pages.

## 0.5.0

Released 2026-05-11.

### Configuration and persistence

- The canonical database moved to
  `~/.molcrafts/molq/config/jobs.db`.
- The canonical profile file moved to
  `~/.molcrafts/molq/config/config.toml`.
- Both paths honor `MOLCRAFTS_HOME`.
- `JobStore` now requires an explicit path; `Submitor` still opens the
  canonical store automatically.

Existing files under `~/.molq/` are not migrated automatically.

### SSH and remote workspaces

- SSH config discovery exposes named OpenSSH hosts as cluster candidates.
- `Cluster.from_ssh_alias()` resolves effective connection settings with
  `ssh -G`.
- `Workspace` and `Project` provide transport-backed upload, download,
  listing, and remote submission helpers.

## 0.4.0

Released 2026-05-02.

- `"local"` became the single no-batch scheduler.
- Every scheduler now routes commands through the selected transport.
- A local scheduler can therefore run on this host or an SSH workstation.
- The former `"shell"` scheduler name was removed.

## 0.3.0

Released 2026-04-18.

- Added `molq watch --all`.
- Added profile loading through molcfg.
- Refined job artifact defaults and CLI inspection.

## 0.1.0

Released 2025-06-24.

Initial beta with local, SLURM, PBS, and LSF backends; typed requests; SQLite
persistence; reconciliation; monitoring; and CLI support.
