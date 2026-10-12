# Watch and notifications

There is no plugin host. `molq watch` asks the serve process for observations and forwards changes that the process already produced. It owns cadence, bounded backoff and the notification URL. None of that is stored on a Cluster. A repeated scheduler failure is printed once until that cluster succeeds again. On resync it also reports each terminal accounting job from the last 24 hours once.

```sh
molq watch --config ./config.json --cluster hpc --interval 5
molq watch --config ./config.json --once
```

Set `client.watch.nerve_endpoint` in the configuration file when a receiver should get the same JSON envelopes. A failed notification does not affect submit, query or cancel.

Other clients use the same RPC. They may choose sampling cadence and route events. They do not reimplement snapshot diff or completion.
