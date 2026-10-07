# Agent-first CLI

Business commands emit JSON-RPC-shaped JSON lines with typed error data. No tables need parsing. Help/version are static and noninteractive. discover returns the versioned method catalog, request schemas and result types. rpc METHOD --params JSON, @file or @- exposes every public operation.

Dedicated commands: clusters list/get/register/update/remove, submit, status, list, observe, cancel, logs and wait. Use --ref with the JobRef itself, not the full submit response. Submit convenience argv is after --; canonical specs are available through rpc jobs.submit.

Runtime entry points: runtime rpc --stdio and runtime serve. observer is a peer RPC client with client-owned cadence and optional notification routing.

| Exit | Meaning |
|---|---|
| 0 | Successful operation; cancellation acceptance is not task completion |
| 1 | Unexpected internal failure |
| 2 | Invalid input / unknown method |
| 3 | Missing destination, file or cache |
| 4 | Runtime, Scheduler or Transport unavailable |
| 5 | Unsupported representation/protocol/channel |
| 6 | Wait/operation deadline |
| 7 | Authentication, permission or native rejection |
| 8 | Partial batch failure |
| 9 | Wait confirms terminal execution failure |
| 10 | Conflict, uncertain mutation or identity mismatch |

No endpoint means temporary stdio Runtime. Set --endpoint or MOLQ_ENDPOINT to use a shared Runtime. MOLQ_TOKEN supplies its credential; --registry selects a stdio registry. Failed auth/version/registry checks do not fall back to a new Runtime.
