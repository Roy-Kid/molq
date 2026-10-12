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

## Shared serve process

Put the listen address and token in the configuration file, then start serve:

```json
{"serve": {"host": "127.0.0.1", "port": 17891, "token": "replace-with-your-own-long-secret"}}
```

```sh
molq serve --registry ./registry.db --config ./config.json
```

Clients set `client.endpoint` and `client.token` in that same kind of file, or pass them to the SDK constructor. HTTP and WebSocket use the same RPC implementation as stdio. A token is required even on loopback; deploy HTTPS/WSS through existing infrastructure. There is no web UI.

One registry normally has one active serve process. Temporary stdio instances have separate cache, event rings and cursors. SQLite protects short accidental write overlap and does not synchronize their observations.

Periodic observation is optional:

```sh
molq watch --registry ./registry.db --config ./config.json --cluster local
```

`watch` chooses cadence and notification delivery. The serve process computes snapshots, completion and changes. Subscriptions deliver changes that were already observed.
