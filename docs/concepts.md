# Concepts

`molq serve` is the single business implementation. It is ordinary Go packages for the protocol, Scheduler, Transport, registry, observation and RPC. It can be a finite stdio process or a shared network service.

Clients are peers: the CLI, sync and async Python objects, and the TypeScript SDK use public RPC. `molq watch` is the optional client that chooses cadence and notification. Clients construct values and project methods. They do not render scheduler requests, interpret native state, merge defaults or open the registry. There is no web UI.

Cluster is a durable computing destination; SSH alias is how to reach it. Transport performs I/O; Scheduler owns native semantics. A JobRef identifies a registry, stable Cluster ID, native ID and native submit incarnation. Cluster rename preserves identity; changing Scheduler/Transport/root requires a new Cluster.

A Job is one allocation, independent of the number of execution units. The serve process returns canonical snapshots, freshness, coverage and completion. Missing or unavailable evidence is unknown, never confirmed terminal. Cancellation acceptance is separate from observed cancellation.

See [the full architecture](spec/molq-1-0-runtime-spec.md).
