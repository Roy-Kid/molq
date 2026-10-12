# Agent-first CLI

`molq --help` lists the commands in plain text. `molq <command> --help` explains one command. `molq ping` asks the selected serve process for one hello. `molq health` reports ready or not. `molq doctor` explains a failed check. None of them submits a job.

Business commands print one JSON object, including errors. `discover` returns the method catalog, request schemas, and result types. `rpc METHOD --params JSON`, `@file`, or `@-` calls any public operation.

Job commands: clusters, submit, status, list, observe, history, cancel, logs, and wait. `--ref` is the JobRef, not the whole submit response. Submit takes argv after `--`, or `--spec`. Use one of those, not both.

| Exit | Meaning |
|---|---|
| 0 | Successful operation; cancellation acceptance is not task completion |
| 1 | Unexpected internal failure |
| 2 | Invalid input / unknown method |
| 3 | Missing destination, file or cache |
| 4 | Runtime, Scheduler or Transport unavailable |
| 5 | Unsupported representation/protocol/channel |
| 6 | Wait/operation deadline |
| 7 | Authentication, permission or native rejection |
| 8 | Partial batch failure |
| 9 | Wait confirms terminal execution failure |
| 10 | Conflict, uncertain mutation or identity mismatch |

No endpoint means a temporary stdio serve process. The endpoint and token come from the configuration file or the SDK constructor. `--registry` selects a stdio registry. Failed auth, protocol, or registry checks do not open another process.

## Names, comments and history

Simple argv submission accepts `--name` and `--comment` before `--`. With `--spec`,
set `scheduling.name/comment` in the spec; mixing convenience fields with a spec
is rejected. Slurm sends comment as a native argv value, LSF uses native `-Jd`;
PBS and Shell reject user comments. The preview script does not encode the comment:
it remains in the returned spec and is supplied as a native submit argument.

```sh
molq submit Arrhenius --name smoke-cpu --comment "CPU smoke test" -- hostname
molq list Arrhenius --state running --name smoke-cpu
molq history Arrhenius --state failed --since 2026-10-06T00:00:00Z --until 2026-10-08T00:00:00Z
molq history Arrhenius --refs @refs.json
molq rpc config.reload
```

Range history queries the target login account. Time bounds require RFC3339
with timezone and filter ended-at `[since, until)`; default is the preceding
24 hours. `--state` is repeatable and distinguishes failed/cancelled/timed_out.
`--limit` defaults to 100 and may be 1–1024. Ref mode is mutually exclusive with
range fields. Slurm range discovery requires native JSON output; there is no text
fallback. PBS/LSF/Shell range queries return unsupported, while explicit refs work.

History results include query bounds, source, observation time, freshness and
coverage. Truncated results or bounded native output return incomplete coverage;
narrow the window. A successful empty result means no retained matching records,
not proof that no historical task failed. Native outages are explicit errors.
Slurm comment retention requires site accounting configuration such as
`AccountingStoreFlags=job_comment`; see [Slurm accounting](https://slurm.schedmd.com/sacctmgr.html).

Global `--config` chooses the JSON/YAML file. `serve`, `rpc` and `watch` accept
it too. When it is omitted, the CLI loads `~/.molcrafts/molq/config.json` if
that file exists.
A database that is not the current registry layout is rejected and not migrated.
