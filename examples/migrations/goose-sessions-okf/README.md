# Goose sessions → portable OKF

This migration showcase turns local [goose](https://goose-docs.ai/) session
history into a portable Open Knowledge Format (OKF) bundle that Memanto can
import with:

```bash
memanto migrate okf examples/migrations/goose-sessions-okf/sample_output/goose-okf
```

goose is local-first: its session data stays on the user's machine. Current
goose releases store CLI and Desktop conversations in a local SQLite database,
while older releases left legacy `.jsonl` session files behind. This example
reads those local records, extracts durable memory candidates, redacts private
machine-specific details by default, and writes human-inspectable markdown.

## What this proves

The flow is:

1. Read a real goose session export, a legacy `.jsonl` session, or a read-only
   `sessions.db` copy.
2. Extract session-level memories, user preferences, decisions, and completed
   work facts from the transcript.
3. Write a portable OKF bundle under `memories/`.
4. Validate the generated bundle with Memanto's existing `load_okf_bundle` and
   `map_okf` import path.

That gives goose users an escape hatch from local conversation archives into a
plain markdown memory estate they can inspect, version, import into Memanto, or
carry to another OKF-compatible tool.

## Quickstart

From the repository root:

```bash
python examples/migrations/goose-sessions-okf/goose_sessions_to_okf.py \
  examples/migrations/goose-sessions-okf/fixtures/goose-session-export.json \
  --out examples/migrations/goose-sessions-okf/sample_output/goose-okf \
  --summary examples/migrations/goose-sessions-okf/sample_output/migration-summary.json \
  --force

python examples/migrations/goose-sessions-okf/validate_roundtrip.py \
  examples/migrations/goose-sessions-okf/sample_output/goose-okf \
  --report examples/migrations/goose-sessions-okf/sample_output/parity-report.md
```

The committed fixture mirrors goose's exported session shape: metadata plus a
conversation history. For a real local goose install, point the converter at one
of these paths instead:

- macOS/Linux current storage:
  `~/.local/share/goose/sessions/sessions.db`
- Windows current storage:
  `%APPDATA%\Block\goose\data\sessions\sessions.db`
- legacy macOS/Linux storage:
  `~/.local/share/goose/sessions/*.jsonl`

Use a copy of `sessions.db` if goose is running, so the converter never competes
with the live app for its database file.

## Demo

The sample output includes a short animated terminal walkthrough:

![Goose sessions to OKF demo](sample_output/demo.gif)

## Mapping table

| goose source concept | OKF / Memanto target | Notes |
| --- | --- | --- |
| Session metadata | `event` memory | Preserves session id, description, working directory, timestamps, and source path. |
| User instructions and preferences | `preference` or `instruction` memory | Extracted from phrases such as "always", "prefer", "avoid", "remember", and "do not". |
| Explicit decisions | `decision` memory | Extracted from "decision", "we chose", "use X instead of Y", and similar transcript lines. |
| Assistant completed-work summaries | `fact` memory | Captures durable outcomes such as files changed, checks run, and behavior fixed. |
| Tool failures / blocked states | `error` memory | Keeps operational lessons from failed shell commands or tool results. |

Every entry includes `x_memanto` provenance fields so Memanto's OKF importer can
round-trip source, source reference, confidence, and timestamps.

## Privacy model

Redaction is on by default. The converter masks:

- email addresses
- obvious access tokens and API key strings
- Unix home paths such as `/Users/alex/project`
- Windows home/AppData paths such as
  `C:\Users\Alex\AppData\Roaming\Block\goose`

Pass `--no-redact` only when creating a private archive.

## Generated sample

`sample_output/` was produced from the committed fixture with the quickstart
command above. It includes:

- `goose-okf/` — OKF bundle with markdown memories and metrics
- `migration-summary.json` — source count, mapped count, and type breakdown
- `parity-report.md` — deterministic recall-parity check over the OKF import
