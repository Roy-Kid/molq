# Clusters, Scheduler and Transport

Register destinations explicitly. No unknown name silently becomes a local target.

```json
{"name":"hpc","scheduler":"slurm","transport":{"kind":"ssh","alias":"research"},"target_root":"/scratch/user/molq","launcher":"srun","defaults":{"resources":{"tasks":4,"cpus_per_task":2}}}
```

OpenSSH resolves research using the user's configuration and manages authentication, jumps and multiplexing. System ssh is invoked in noninteractive BatchMode. Neither Cluster nor Transport copies connection settings or maintains a Python session pool.

Mappings in this release:

| Scheduler | Accurate mappings | Explicit restrictions |
|---|---|---|
| shell | Detached Bash execution, original launch/process/exit evidence | No formal batch resource/scheduling requests |
| slurm | Nodes/tasks/threads, per-node memory, wall time, GPU total/per-node, per-node nvidia_mps, scheduling/dependencies, srun steps | One accelerator request; no after_started mapping |
| pbs | Explicit openpbs JSON/select dialect, evenly distributed tasks, per-node memory/GPU, time, common scheduling/dependencies | No QoS/reservation/exclusive/model/MPS mapping |
| lsf | Single-node single-thread task layout, time, common scheduling/dependencies, explicit site MPI | Memory, GPU/MPS and other layouts rejected without an exact site mapping |

There is no capability inventory, probing or negotiation. jobs.validate verifies schema, layout and exact representation. Actual allocation resources/configuration/permissions remain the native scheduler's decision.

Slurm reads queue then accounting; PBS reads retained extended job facts; LSF reads current/recent retained native history. Missing retention/evidence yields unknown/unavailable. HPC regression tests use fixtures, not a live cluster.

Native references: [Slurm squeue](https://slurm.schedmd.com/squeue.html), [Slurm sacct](https://slurm.schedmd.com/sacct.html), [LSF output fields](https://www.ibm.com/docs/en/spectrum-lsf/10.1.0?topic=information-customize-job-output).
