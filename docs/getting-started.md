## Quickstart

Install Python 3.12 or later:

```sh
pip install molcrafts-molq
molq --registry ./registry.db clusters register --definition '{"name":"local","scheduler":"shell","target_root":"/tmp/molq-target"}'
molq --registry ./registry.db submit local -- echo hello
```

The submit response contains a stable registry-qualified JobRef. Save it and pass it to status, logs, cancel or wait:

```sh
molq --registry ./registry.db status --ref @job-ref.json
molq --registry ./registry.db wait --ref @job-ref.json --timeout 60
molq discover
```

Use the OOP Python client without starting a service:

```python
from molq import Molq

with Molq(registry="registry.db") as mq:
    mq.clusters.register(
        name="local", scheduler="shell", target_root="/tmp/molq-python"
    )
    job = mq.cluster("local").submit(argv=["echo", "hello"])
    print(job.wait(timeout=60)["completion"])
    print(job.logs()["text"])
```

When no endpoint is configured, native clients start a temporary stdio Runtime. Accepted Shell jobs detach from the client and retain original target launch/exit receipts; scheduler jobs already belong to the scheduler. Restarting a client can query a saved JobRef.

## Shared Runtime and Web

```sh
export MOLQ_TOKEN='replace-with-your-own-long-secret'
molq runtime serve --registry ./registry.db --host 127.0.0.1 --port 17891
```

Open http://127.0.0.1:17891/ and enter the token. Connect other clients to that same endpoint using MOLQ_ENDPOINT and MOLQ_TOKEN. HTTP and WebSocket use the same RPC implementation as stdio. A token is required even on loopback; deploy HTTPS/WSS through existing infrastructure.

One registry normally has one active Runtime. Configure an explicit endpoint for shared clients. Temporary stdio instances have separate cache, event rings and cursors; SQLite protects short accidental write overlap, without synchronizing their observations.

Runtime performs finite requested operations. Periodic observation is optional:

```sh
molq --endpoint http://127.0.0.1:17891 observer --cluster local --interval 5
```

Observer chooses cadence and notification delivery; Runtime computes snapshots, completion and changes. Subscriptions passively distribute already observed changes and do not poll a scheduler.
