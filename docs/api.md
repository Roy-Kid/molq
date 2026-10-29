# Python API

Create a destination with `submit(...)`, decorate a function, and yield `JobSpec`.
Each yield receives a `Job`; the function's `return` is its result.

## Define and submit

```python
import json

from molq import JobSpec, submit

local = submit("dev", "local")


@local
def hello(name):
    job = yield JobSpec.argv(["echo", f"hello {name}"])
    return job


job = hello("molq")
job.wait(timeout=30)
print(json.dumps(job.logs(), ensure_ascii=False))
local.close()
```

`submit("dev", "local")` binds a local Shell destination. Jobs run in
`~/.molcrafts/molq/jobs` on the execution machine. Repeating an
explicit binding reuses the destination if the supplied fields match.
Use `submit("dev")` or `submit("hpc")` to select an existing destination.
See [clusters](schedulers.md) for SSH and scheduler settings.

The function runs on your submission machine. Each yield submits one allocation;
multiple yields submit separate allocations. Use an [execution plan](jobs.md#execution-plans)
for multiple commands inside an allocation. Ordinary functions retain their
normal return value and do not submit. Decoration itself performs no RPC.

Requests must be `JobSpec` values. Raw lists and dictionaries are rejected.
Submission errors propagate without automatic resend.

## Async Python

Use `asubmit(...)` and await decorated calls and job operations:

```python
import asyncio
import json

from molq import JobSpec, asubmit


async def main():
    local = await asubmit("dev", "local")

    @local
    def hello(name):
        job = yield JobSpec.argv(["echo", f"hello {name}"])
        return job

    try:
        job = await hello("molq")
        result = await job.wait(timeout=30)
        if result["completion"]["successful"]:
            print(json.dumps(await job.logs(), ensure_ascii=False))
    finally:
        await local.close()


asyncio.run(main())
```

The builder remains a synchronous generator. Each yield receives an `AsyncJob`.
Cancelling the decorated call leaves accepted allocations running.

## Job handles

`job.status()`, `job.wait()`, `job.logs()` and `job.cancel()` operate on the
submitted allocation. Save `job.ref` to return later. Results are dictionaries;
request values are frozen dataclasses. All durations are seconds. SDK calls are silent; serialize returned values with
`json.dumps(...)` for machine-readable stdout.

A destination also exposes `submit(spec)`, `validate(spec)`, and `preview(spec)`;
all three require a `JobSpec`. `transfer(source_path, destination,
destination_path, *options)` copies a path to another destination handle with
one rsync run. Close the destination when finished. For file I/O on a cluster,
use [`mq.Path`](remote-files.md#cluster-paths).

## Client operations

`Molq` and `AsyncMolq` provide registry, configuration, saved references and batch
operations. They use the same RPC connection as destination handles:

```python
import json

from molq import Molq

mq = Molq()
try:
    print(json.dumps(mq.clusters.list(), ensure_ascii=False))
finally:
    mq.close()
```

Pass `endpoint`, `token`, `registry`, or `config` to `submit`, `asubmit`, or the
client constructor. Submit and transfer go through destination methods.
Failures raise [MolqError](reference/utilities.md#errors).

| Reference | Contents |
|---|---|
| [Sync API](reference/core.md) | `submit`, destinations, jobs and clients |
| [Async API](reference/async.md) | `asubmit` and async operations |
| [Request values](reference/types.md) | Resources, scheduling, commands and plans |
| [TypeScript](reference/typescript.md) | Generator decorators in Node and browsers |
| [RPC and errors](reference/utilities.md) | Methods, wire limits and failure outcomes |
