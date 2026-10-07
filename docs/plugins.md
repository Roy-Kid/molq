# Observer and notifications

The 0.8 daemon/plugin host and built-in Nerve plugin are removed. The optional Observer is a peer client that requests Cluster observations, consumes Runtime-produced changes and forwards notifications. It owns cadence, bounded backoff and notification routes; no policy is stored on Cluster.

```sh
molq --endpoint http://127.0.0.1:17891 observer --cluster hpc --interval 5
molq --endpoint http://127.0.0.1:17891 observer --once --nerve-endpoint http://127.0.0.1:17890/ingest
```

The supplied notification receiver must accept Runtime change envelopes as JSON. No compatibility with the old Nerve plugin's custom rollup format is implied. Notification failures are fail-open and cannot affect scheduler operations.

Other observers/UI integrations use the same RPC. They may choose sampling cadence and route events, but must not duplicate Runtime's state diff or terminal/completion logic.
