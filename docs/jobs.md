# Submit allocations and execution plans

A request has independent resources, scheduling and execution sections. Memory is a decimal string of per-node bytes; nodes, tasks and cpus_per_task define the allocation. A unit describes argv, shell or script, optional env/cwd/output, and direct or explicit MPI launch.

```python
from molq import Execution, ExecutionUnit, JobSpec, Parallel, Sequence, UnitRef

spec = JobSpec(execution=Execution(
    units=(
        ExecutionUnit.argv("a", ["echo", "a"]),
        ExecutionUnit.argv("b", ["echo", "b"]),
        ExecutionUnit.argv("finish", ["echo", "done"]),
    ),
    plan=Sequence((Parallel((UnitRef("a"), UnitRef("b"))), UnitRef("finish"))),
))
# mq.cluster("local").preview(spec) and .submit(spec) use the same renderer.
```

Each unit appears exactly once in its explicit plan. A single unit gets an implicit unit reference. Sequence stops at the first failure. Parallel starts branches, waits for all started branches, and returns the first failing branch in plan order. A batch allocation with multiple units requires an explicit task budget.

MPI requires launch.ranks and a configured Cluster launcher; there is no tool probing. Slurm srun can represent native steps/placement; other mappings require explicit site MPI bindings. Runtime validates CPU/task budgets before submission.

Dependencies reference allocations in the same Cluster and are identity-checked before submission. Their syntax and accurate representation belong to Scheduler. Request preview does not assert resource availability or permissions.

A request_key deduplicates jobs.submit/cancel only within one Runtime for a bounded interval (10 minutes, 1024 retained operations). After restart or dispatch disconnection, reconcile native state instead of automatically resending an uncertain mutation.
