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
