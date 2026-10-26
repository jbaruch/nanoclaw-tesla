---
alwaysApply: true
description: Vehicle access follows protected host policy and fresh Tessie inventory
---

# Vehicle Selection

## Host Predicate

- Host-protected `DATA_DIR/tessie-authority/policy.json` version 2 selects `non_archived` or `explicit` mode.
- `non_archived` is the owner's dynamic opt-in for every current or future active vehicle with recognized native OWNER or DRIVER access.
- The host derives that admitted set from fresh inventory on each operation.
- Missing or unknown access and archived vehicles grant no dynamic access.
- Unnamed vehicles receive stable VIN aliases; duplicate names receive deterministic disambiguation.
- `explicit` mode requires a protected VIN entry plus current OWNER/active proof, or a protected `shared: true` entry and live presence.
- Empty chat roles authorize nobody in either mode.

## Agent Selection

- Pick a vehicle using an alias or VIN returned by the host.
- Ask which vehicle when the script reports `selector_required`.
- Use the current exact alias/action confirmation printed by the plan.
- A renamed or archived vehicle requires a fresh authorized plan before any new effect.
- The host owner maintains protected policy; agent files and role variables grant nothing.
- A denied vehicle exits 4; report its diagnostic and stop.

## Discovery

- `tessie-vehicles.py` lists only currently admitted vehicles for an authorized chat.
- Historical completed receipts never grant a new effect or permit replay.
