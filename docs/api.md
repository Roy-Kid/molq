# Python and TypeScript API

Python exports Molq, AsyncMolq, Cluster, Job and JobCollection, plus immutable value constructors. Runtime validation/default merging/Scheduler mapping are accessed through RPC.

```python
from molq import AsyncMolq

async def example():
    async with AsyncMolq(endpoint="http://127.0.0.1:17891", token="your-long-token") as mq:
        job = await mq.cluster("hpc").submit(argv=["hostname"])
        result = await job.wait(timeout=60)
        return result
```

TypeScript provides the same Molq/Cluster/Job/JobCollection projections and generated JobSpec/JobRef/result types. Node can use StdioWire; browsers use HttpWire and WebSocket subscription. The SDK source/package is sdk/typescript.

```typescript
import {Molq} from "@molcrafts/molq";
const mq = Molq.http("http://127.0.0.1:17891", "your-long-token");
const job = await mq.cluster("hpc").submitArgv(["hostname"]);
console.log(await job.wait(60000));
await mq.close();
```

All clients expose generic rpc for the full method catalog. Python durations for wait are seconds; TypeScript wait arguments are milliseconds. Request/result field names are the canonical snake_case wire names.

See [core API](reference/core.md), [values](reference/types.md) and [RPC contract](reference/utilities.md).

## Native history discovery

```python
from molq import Molq

with Molq() as mq:
    cluster = mq.cluster("Arrhenius")
    queue = cluster.list(states=["running"], name="science")
    history = cluster.history(
        since="2026-10-06T00:00:00Z", until="2026-10-08T00:00:00Z",
        states=["failed"], limit=100,
    )
    refs = [s["ref"] for s in history["snapshots"]]
    # An empty set needs no explicit-ref query.
    if refs:
        observed = cluster.history(refs=refs)
```

AsyncCluster provides the same methods with `await`. TypeScript Cluster supports
`list({states, name})` and `history({since, until, states, name, limit})` or
`history({refs})`. All are direct public RPC projections.

Range history returns terminal jobs ended in `[since, until)` for the current
target account, including jobs submitted outside molq. Only Slurm implements
range discovery in this release. Default range is 24 hours; missing native
metadata is `null`, and unavailable accounting never becomes a successful empty
query. Inspect coverage and query freshness before assuming complete results.
Identity includes incarnation; reused native IDs remain distinct. History
retention is owned by the scheduler. Runtime restart clears diff baselines and
cursors; it does not erase native accounting.

`Molq(config=...)` and `AsyncMolq(config=...)` select the configuration file for a temporary stdio serve process. Pass `registry=` for a registry other than the default. With HTTP, the configuration file belongs to the remote serve process. Connection settings are constructor arguments or the configuration file, not environment variables.
