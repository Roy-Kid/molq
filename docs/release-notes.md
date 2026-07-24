# Release Notes

## 0.6.0

Release date: 2026-07-22

### Plugin host

- `molq.plugin` host: official builtins + third-party entry points
  (`molq.plugins` group)
- `Submitor(plugins=..., plugin_configs=...)`; daemon defaults to
  **nerve** when no `[plugins]` section is set
- Official **nerve** plugin ships with molq (rollup status → local Nerve
  menu bar; display-only, fail-open)

### Documentation & packaging

- Docs site on **molcrafts-zensical-theme** (hero home, product accent,
  light/dark)
- CLI help reorganized by Jobs / History / Live / Setup; `molq plugins list`
- Config / DB default paths documented as molcfg
  (`~/.molcrafts/molq/config/…`, honouring `MOLCRAFTS_HOME`)

## 0.5.0

See [CHANGELOG.md](../CHANGELOG.md) for the 0.5.0 store-path and Cluster /
workspace notes.

## 0.1.0

Release date: 2025-06-24

Initial beta release of `molq`.

### What's included

- `Submitor` and `JobHandle` as the public job submission surface
- Typed submission models: `Memory`, `Duration`, `Script`, `JobResources`,
  `JobScheduling`, `JobExecution`
- Schedulers for local execution, SLURM, PBS, and LSF
- SQLite-backed persistence with reconciliation and monitoring
- CLI commands for submit, inspect, watch, cancel, and log access
