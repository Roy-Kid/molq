# @molcrafts/molq 0.9.0

Peer OOP client for molq's public RPC, using generated request/result types.

```typescript
import {Molq} from "@molcrafts/molq";
const mq = Molq.http("http://127.0.0.1:17891", "your-long-token");
const job = await mq.cluster("hpc").submitArgv(["hostname"]);
console.log(await job.wait(60000));
console.log(await job.logs());
await mq.close();
```

Node without a running service:

```typescript
import {Molq, StdioWire} from "@molcrafts/molq/node";
const mq = new Molq(new StdioWire(["molq", "runtime", "rpc", "--stdio"]));
console.log(await mq.cluster("hpc").list());
await mq.close();
```

Install the molcrafts-molq Python package for this Runtime entry point. Shared clients use the same endpoint; independent stdio processes have independent cache/events/cursors. No connection fallback or automatic uncertain-mutation resend occurs.

Cluster registration is explicit. Resources/Scheduling/Execution and plans use canonical wire fields. Generic rpc exposes all methods. Wait uses milliseconds and reads Runtime completion. Closing a client never cancels an accepted job.

Run npm ci, npm test and npm pack --dry-run. This package contains no Scheduler, SSH or SQLite implementation. Windows clients use remote POSIX targets; local Shell execution requires POSIX/Bash.

Queue filters: `cluster.list({states:["running"], name:"science"})`.
Native Slurm history: `cluster.history({states:["failed"], since:"2026-10-06T00:00:00Z", until:"2026-10-08T00:00:00Z"})`.
Inspect returned coverage/query metadata; history uses native retention and ended-at bounds.
For custom stdio registries, include both `--registry` and `--config` in StdioWire's command.

[NVIDIA MPS examples](../../docs/nvidia-mps.md) cover native Slurm resources and ordinary user-managed MPS payloads with generated JobSpec types.
