# Concepts

Runtime is the single business implementation, assembled from ordinary domain, Scheduler, Transport, registry, observation and RPC modules. It can be a finite stdio process or a shared network service.

Clients are peers: CLI, sync/async Python OOP, TypeScript OOP, Web and Observer use public RPC. Their code constructs values, projects methods and chooses foreground/background cadence. Clients do not render scheduler requests, interpret native state, merge defaults or open the registry.

Cluster is a durable computing destination; SSH alias is how to reach it. Transport performs I/O; Scheduler owns native semantics. A JobRef identifies a registry, stable Cluster ID, native ID and native submit incarnation. Cluster rename preserves identity; changing Scheduler/Transport/root requires a new Cluster.

A Job is one allocation, independent of the number of execution units. Runtime returns canonical snapshots, freshness, coverage and completion. Missing or unavailable evidence is unknown, never confirmed terminal. Cancellation acceptance is separate from observed cancellation.

See [the full architecture](spec/molq-1-0-runtime-spec.md).
