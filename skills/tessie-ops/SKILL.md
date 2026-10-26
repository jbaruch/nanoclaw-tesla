---
name: tessie-ops
description: "Reads and controls the owner's Tesla vehicles through the Tessie REST API using deterministic scripts: list vehicles, check the allowlist, read battery/charging/climate/locks/tires/firmware/drives and authorized drivers from cache without waking the car, and send confirmed controls (lock, unlock, climate, charging, charge limit, share destination, flash, drive tags). Triggers: 'is the car locked', 'where is the car', 'who can drive the car', 'list Tesla drivers', 'tesla battery', 'tire pressure', 'lock the tesla', 'unlock the tesla', 'start climate', 'charge limit', 'send address to the car', 'tag my drives', 'tessie', 'my vehicles'."
---

# Tessie Ops

This skill is an action router — pick the step that matches the user's intent and execute only that step. Do not run other steps; do not parallelize.

Every Tessie call is one of the scripts below. Their docstrings own arguments, output shape and exit codes; this skill names which script serves which intent. Production scripts use the version-1 native host broker; missing authority denies without HTTP fallback. Protected host policy grants vehicle/chat access. The existing OneCLI gateway injects the vaulted key; never ask for or print a token (`rules/tessie-credentials.md`). Exit 4 means the allowlist or chat authorization denied the request: report the `denied_reason` and stop. Any other non-zero exit: report the stderr diagnostic and stop.

## Step 1 — List Vehicles

Use when the user asks which vehicles are available. Finish here.

```bash
python3 /home/node/.claude/skills/tessl__tessie-ops/scripts/tessie-vehicles.py
```

The host returns admitted vehicles only. An owner may add `--include-denied` for client-side explanations within that projection. Contract: `scripts/tessie-vehicles.py` docstring.

## Step 2 — Check The Allowlist

Use when the user asks about the setup or why a vehicle is refused. Finish here.

```bash
python3 /home/node/.claude/skills/tessl__tessie-ops/scripts/tessie-allowlist.py show
python3 /home/node/.claude/skills/tessl__tessie-ops/scripts/tessie-allowlist.py resolve --vehicle "<alias>"
```

Only the host owner edits the protected policy (`docs/setup.md`). Agent state and role variables grant nothing.

## Step 3 — Read Vehicle State

Use for battery, charging, climate, locks, tires, firmware alerts, idle drain or drive history. Finish here.

```bash
python3 /home/node/.claude/skills/tessl__tessie-ops/scripts/tessie-read.py <kind> --vehicle "<alias>"
```

`<kind>` is `status`, `state`, `battery`, `tire_pressure`, `firmware_alerts`, `consumption_since_charge`, `last_idle_state` or `drives`. The read uses Tessie's cache and never wakes the car; if `vehicle_status` is not `awake`, say the data comes from cache. Omit `--vehicle` to use the default vehicle; ask the user when the script reports `selector_required`.

## Step 4 — Read Location

Use only in an owner chat and only when the user asks where the car is. Finish here.

```bash
python3 /home/node/.claude/skills/tessl__tessie-ops/scripts/tessie-read.py location --include-location --vehicle "<alias>"
```

Follow `rules/location-privacy.md`: never repeat coordinates or addresses outside an owner chat. A denied location read is final; do not look for the position in other output.

## Step 5 — List Authorized Drivers

Use when an owner asks who can drive the vehicle. Finish here.

```bash
python3 /home/node/.claude/skills/tessl__tessie-ops/scripts/tessie-read.py drivers --vehicle "<alias>"
```

Drivers are owner-only. Exit 4 is final; report it and stop.

## Step 6 — Preview A Control

Use for every control request, before Step 7. Show the user the plan.

```bash
python3 /home/node/.claude/skills/tessl__tessie-ops/scripts/tessie-command.py <action> --vehicle "<alias>" --dry-run
```

`<action>` is `lock`, `unlock`, `start_climate`, `stop_climate`, `set_temperatures` (`--temperature`), `start_charging`, `stop_charging`, `set_charge_limit` (`--percent`), `share` (`--value`) or `flash`. State the vehicle (alias and VIN suffix) and the action to the user. Destination sharing also requires an owner chat; the script refuses other chats before a plan or effect. Proceed immediately to Step 7 when the user's request already authorizes that action on that vehicle. Otherwise finish here and wait for the missing authorization.

## Step 7 — Run A Control

```bash
python3 /home/node/.claude/skills/tessl__tessie-ops/scripts/tessie-command.py <action> --vehicle "<alias>" --confirm "<alias>:<action>"
```

Pass the same parameters as Step 6 and the `confirm_with` phrase the plan printed. Report the `status` field:

- `confirmed` — Tessie accepted it and a fresh state read shows the change
- `accepted` — Tessie accepted it; the action has no state field to check (flash, share)
- `unconfirmed` (exit 3) — Tessie accepted it, the state did not confirm it; say it is not verified
- `failed` (exit 1) — Tessie refused it

Never retry on your own. Finish here.

## Step 8 — Confirm Vehicle State

Use when the user asks whether an earlier control took effect. Finish here.

```bash
python3 /home/node/.claude/skills/tessl__tessie-ops/scripts/tessie-confirm.py <action> --since <sent_at_epoch> --vehicle "<alias>"
```

Pass the earlier control's `sent_at_epoch` (unix seconds), plus `--temperature` or `--percent` when the action took one. Missing or failed confirmation retains known acceptance; never resend it automatically.

## Step 9 — Preview Drive Tags

Use when the user asks to tag drives for later reporting. Show the plan's
vehicle, drive IDs and tag to the user. Proceed immediately to Step 10 when the
original request already authorizes those drive IDs, tag and vehicle. Otherwise
finish here and wait for the missing authorization.

```bash
python3 /home/node/.claude/skills/tessl__tessie-ops/scripts/tessie-command.py set_drive_tag --drives "<ids>" --tag "<tag>" --vehicle "<alias>" --dry-run
```

## Step 10 — Apply Drive Tags

Use after the preview has been shown and the user's request authorizes those
drive IDs, tag and vehicle. Pass the exact `confirm_with` phrase from the plan.

```bash
python3 /home/node/.claude/skills/tessl__tessie-ops/scripts/tessie-command.py set_drive_tag --drives "<ids>" --tag "<tag>" --vehicle "<alias>" --confirm "<alias>:set_drive_tag"
```

Report the accepted/refused result and finish here. Never replay uncertainty.
