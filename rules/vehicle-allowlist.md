---
alwaysApply: true
description: Only allowlisted OWNER vehicles are addressable; shared and unnamed vehicles stay excluded
---

# Vehicle Allowlist

## Default Deny

- A vehicle is addressable only when its VIN is listed in `/workspace/state/tessie-ops/allowlist.json`
- The live Tessie row must also report `access_type` `OWNER` and `is_active` true
- Narrow exception for a vehicle the owner marked `"shared": true` in that file
- Preconditions (all required):
  1. The VIN is listed in the allowlist
  2. The owner set `shared` on that entry
  3. The VIN appears in Tessie's live inventory
- Every other vehicle stays excluded, whatever its alias or display name

## What the Agent Does

- Pick a vehicle by allowlist alias or by the VIN of an allowlisted vehicle
- Ask which vehicle when `tessie-ops` reports `selector_required`
- Never write or edit the allowlist file; the owner maintains it
- Never address a `DRIVER`, `null`-access or inactive row
- A denied vehicle exits 4 with a `denied_reason`; report it and stop

## Discovery

- `tessie-vehicles.py` lists addressable vehicles for any authorized chat
- Only an owner chat sees the denied summary, and it carries no coordinates
