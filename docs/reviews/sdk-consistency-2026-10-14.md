# SDK consistency and machine output review

Scope: Python sync/async, TypeScript Node/browser, CLI and watch. Review follows
molq 0.9's RPC-only client contract. Earlier Submitor/Pydantic skill rules do not
apply to this replacement architecture.

## Shared public contract

| Area | Contract |
|---|---|
| Submission | Destination decorator; each yielded JobSpec receives a Job; preserve builder arguments and return |
| Request operations | submit, validate and preview take JobSpec; no TS-only submitArgv |
| Time | All public deadlines, intervals and freshness ages use seconds |
| Errors | kind, message, outcome and context; preserve unknown mutations through cleanup |
| Connections | Lazy explicit connection; invalid endpoint cannot select stdio; close preserves accepted allocations |
| SDK stdout | Silent; callers serialize values explicitly |
| CLI stdout | JSON-RPC result/error envelopes, including help, version and diagnostics |
| Watch stdout | One JSON envelope per line; failures have meaningful exit codes |
| Diagnostics | stderr; no banners, tables or raw target logs mixed into stdout |

## Resolved findings

- Unified TS milliseconds with Python/CLI seconds and removed its argv-only path.
- Rejected nonfinite deadlines, unrepresentable JSON and invalid connection options
  before dispatch. Both codecs reject malformed envelopes and invalid UTF-8.
- Preserved ErrorData context keys and the original failure during cleanup.
- Quarantined failed stdio sessions; bounded shutdown and HTTP cancellation.
- Shared concurrent TS handshakes and copied allocation references before use.
- Converted CLI help/version/probes and Python startup failures to structured JSON.
- Preserved task arguments after `--`; fixed watch exit status and duplicate errors.
- Updated every public example to JSON serialization and verified example stdout.

## Review dimensions

- Architecture: PASS. Peer clients use public RPC; schema/client generation matches.
- Performance: PASS. Bounded frames/processes, shared handshake, batch observation.
- Documentation: PASS. Manual and README use current APIs, seconds and JSON output.
- System safety: PASS. No resend of uncertain mutations; accepted jobs survive close.
- Code quality: PASS. Ruff/types/SDK compilation and source files below 800 lines.
- Immutability: PASS. Frozen Python request values and copied handle references.

Unresolved critical/high findings in this review: 0.

## Verification

- Python: 163 tests passed; coverage 89.62%.
- TypeScript: 27 tests passed, plus compile-time argument/result assertions.
- Go: all packages passed, including CLI/watch output and exit tests.
- Generated contract/clients, lint, formatting, types and strict manual build passed.
- Build and isolated installation checks cover Python and npm artifacts.

Native execution evidence in this review is local Shell plus the real HTTP/stdio
serve process. Protocol peer fixtures establish framing and failure behavior.
