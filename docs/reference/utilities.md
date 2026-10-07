# Public RPC contract

Canonical wire schema: src/molq/protocol/v1.json. Its declarative source is tools/build_contract.py. tools/generate_clients.py produces Python TypedDicts, TypeScript types and the async Python projection. Generated drift is checked before release.

Methods: molq.hello, schema.discover; clusters.list/get/register/update/remove; jobs.validate/preview/submit/get/get_many/list/history/cancel/cancel_many/observe; events.subscribe; logs.read; files.read/write/transfer; config.get/set; presets.list/get/set.

Protocol major is 1, release is 0.9.0. JSON-RPC 2.0 uses named params, batches up to 128, frames up to 1 MiB. Every mutation requires a request ID. The hello handshake exposes protocol/registry/Runtime identities and method names; it is not a feature negotiation API.

Error data includes kind, message, outcome (not_applied/applied/unknown) and context. OUTCOME_UNKNOWN after dispatch is not permission to automatically retry a submit. Reconcile native truth first.

::: molq.errors
