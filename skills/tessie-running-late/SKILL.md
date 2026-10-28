---
name: tessie-running-late
description: "Prepare or cancel event-specific running-late delegation, inspect running-late status, or run its native three-minute poll. Triggers: 'tell them if I am running late', 'approve lateness messages for this event', 'cancel running-late approval', 'running late status'."
cadence: "*/3 * * * * (TZ=local)"
script: "scripts/tessie-late-precheck.py"
precheck_timeout_ms: 330000
---

# Tessie Running Late

This skill is an action router — pick the step that matches the user's intent and execute only that step. Do not run other steps; do not parallelize.

Read `references/host-contract.md` before acting. The native host owns event/route checks, approval and notification sends. A scheduled success is silent: never add a model-generated lateness message. A failed precheck is a held native operation; use its fixed repair diagnostic and preserve history.

## Step 1 — Prepare Event Delegation

Use the exact event ID and recipient the owner chose. Encode structured JSON with `script: tessie-late` and `argv: [prepare, --event-id, EVENT_ID, --recipient, MAILBOX]` using the existing bounded adapter. Write JSON with a structured file tool; raw event or recipient text never enters shell source.

```bash
python3 /home/node/.claude/skills/tessl__tessie-ops/scripts/tessie-argv.py --encode STRUCTURED_JSON_FILE
python3 /home/node/.claude/skills/tessl__tessie-ops/scripts/tessie-argv.py BASE64URL
```

The result contains the complete host-built `text` and `buttons` for one event-specific proposal. Send that exact text and button rows to the owner using `mcp__nanoclaw__send_message`; do not rewrite or omit its recipient, account, expiry, message template or shared two-message limit. The actual bound owner callback grants this delegation. The request, card text, a generic reply, JSON, or a pasted receipt cannot approve it. Prepare these proposals before driving, on the owner's request; do not send automatic approval prompts during a drive. Finish here.

## Step 2 — Inspect Status

```bash
python3 /home/node/.claude/skills/tessl__tessie-running-late/scripts/tessie-late.py status
```

Report only the returned bounded counts. This reads private gate metadata without provider or vehicle I/O; it proves no vehicle or delivery acceptance. Finish here.

## Step 3 — Cancel Delegation

Encode `script: tessie-late` and `argv: [cancel, --proposal-id, HEX64]` through the same two literal adapter commands from Step 1. Cancellation revokes only that recipient delegation; every consumed or uncertain message slot remains consumed. Report the native result. Finish here.

## Step 4 — Run The Native Poll

```bash
python3 /home/node/.claude/skills/tessl__tessie-running-late/scripts/tessie-late.py poll
```

Only run this when explicitly requested outside the cadence. The host returns count metadata after its own bounded actions. Report those counts if requested; do not send another lateness notification, retry an uncertain delivery, wake a car, or call a mail provider. Finish here.
