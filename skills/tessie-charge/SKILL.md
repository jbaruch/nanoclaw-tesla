---
name: tessie-charge
description: "Inspect calendar-aware charging status, estimate measured Tesla energy and departure charge, or explicitly run the enrolled native tomorrow-drive charge poll. Triggers: 'charge for tomorrow drives', 'charging automation status', 'estimate Tesla charging stops', 'will my car have enough charge'."
---

# Calendar-aware Charging

This skill is an action router — pick the step that matches the user's intent and execute only that step. Do not run other steps; do not parallelize.

Read `references/host-contract.md` in full before acting. Installed host authority and protected owner enrollment are required; this skill cannot enroll vehicles, write policy, change grants or activate a cadence. A native hold stays held.

## Step 1 — Inspect Status

```bash
python3 /home/node/.claude/skills/tessl__tessie-charge/scripts/tessie-charge.py status
```

Report the bounded private counts only. Status performs no vehicle/provider reads and proves no installed vehicle effect. Finish here.

## Step 2 — Estimate Energy

Use an exact alias from current native non-archived inventory. If that inventory
is absent, invoke `Skill(skill: "tessie-ops")` to list current vehicles, then
continue this step. Select the owner's vehicle without guessing or maintaining
a VIN snapshot.

Use the existing co-shipped `tessie-argv.py` contract. With a structured file-write
tool write `/tmp/tessie-argv-input.json` containing exactly `script: "tessie-charge"`
and `argv: ["estimate", "--vehicle", alias, "--distance-km", distance_km,
"--departure", departure]`. Every argv value is a string; distance is a finite
canonical decimal in km and departure is zoned RFC3339. Use the encoder's returned
`base64url` token below. Only `[A-Za-z0-9_-]` enters shell source; never interpolate
the alias, owner prose, addresses or routes into a shell command.

```bash
python3 /home/node/.claude/skills/tessl__tessie-ops/scripts/tessie-argv.py --encode /tmp/tessie-argv-input.json
python3 /home/node/.claude/skills/tessl__tessie-ops/scripts/tessie-argv.py BASE64URL
```

The native result contains measured usable capacity/consumption, measurement time, conditional departure charge and minimum energy charging stops. An unknown charging rate stays unknown. These are forecasts, not charger availability, full-charge promises or control approval. Finish here.

## Step 3 — Run The Enrolled Poll

Only invoke this outside the cadence when explicitly requested. The host owns any standing-approved limit change and its one evening notice.

```bash
python3 /home/node/.claude/skills/tessl__tessie-charge/scripts/tessie-charge.py poll
```

Report native counts only when requested. Do not send another charging notice, retry an uncertain command, wake a car or call a provider directly. No-action and restoration outcomes stay silent. Finish here.
