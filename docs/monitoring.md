# Observation, waiting and events

jobs.get/get_many/list/history return snapshots, coverage and shared completion semantics. Consistency is live, bounded (max_age) or cached; cached results explicitly carry age. A failed sample never rewrites a job to lost/failed or terminal.

jobs.observe performs one scoped sample and Runtime-owned diff. Pass its opaque cursor for the next sample. First samples, expired cursors and Runtime restart return resync with no invented completion event. Partial coverage creates no state-change events. Cluster observation queries accounting for previously known jobs that leave the queue.

Job/JobCollection.wait chooses a finite foreground cadence and reads Runtime completion. Closing a client or timing out stops waiting and preserves accepted jobs. Per-RPC response deadlines are separate from the wait cadence.

events.subscribe requires WebSocket or stdio. It returns an event-ring cursor and passively pushes events already produced by observation. It performs no autonomous scheduler queries. Cache and baselines each have a 16 MiB encoded-data budget (4096 entries and 64 scopes by default); the event ring has a 4 MiB/512-event budget. Oversized scopes require resync. These are disposable memory; missed history requires resync.

Use one shared endpoint when Web, CLI, SDK and Observer need the same cache/events/cursors. Concurrent independent stdio sessions do not share observation memory.
