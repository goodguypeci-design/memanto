---
type: "decision"
title: "Decision from payments-api deployment memory"
description: "Extracted from a goose user message."
resource: "goose-session-export.json#1/message-3"
tags: ["goose", "transcript", "user", "decision"]
timestamp: "2026-09-07T18:25:00+00:00"
x_memanto:
  source: "goose-sessions"
  source_ref: "goose-session-export.json#1/message-3"
  confidence: 0.74
  provenance: imported
---

Decision: use Postgres advisory locks for payout reconciliation instead of Redis locks because the transaction boundary is easier to audit.
