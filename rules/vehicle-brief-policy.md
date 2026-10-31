---
alwaysApply: false
applyTo: "skills/tessie-brief/**, skills/morning-brief/** — when producing, collecting or interpreting the optional vehicle morning-summary source"
---

# Read-only vehicle brief

## Authored Scope

- The provider is `jbaruch/nanoclaw-tesla`.
- The authored scope is `skills/tessie-brief/` and the optional `jbaruch/nanoclaw-admin` morning-brief source that consumes it.
- Co-shipped executable target: `skills/tessie-brief/scripts/tessie-brief.py`.
- Co-shipped pure validator target: `skills/tessie-brief/scripts/brief_ipc.py`, function `project(value)`.
- The executable takes no arguments and returns exactly `{wake_agent:false,data}` on exit 0; exit 1 has fixed stderr and no stdout.
- `project(value)` accepts the Host schema1 data object without `lines`, validates its complete fields and returns that object plus canonical literal lines; invalid supported input raises `ValueError` or an unknown-zone error, with no provider I/O.
- The fixed native transport closure is the same provider's `skills/tessie-charge/scripts/charge_ipc.py` and `skills/tessie-ops/scripts/tessie_native.py` plus `skills/tessie-ops/scripts/tessie_core.py`.

## Required Read

- Read the complete `skills/tessie-brief/references/host-contract.md` in this installed provider before producing or using summary output.
- Its full text binds.
- Missing or unreadable content stops the action.
- Resolve only this declared provider's contained regular targets; a copied skill with a substituted provider or linked component refuses.

## Evidence Boundary

- Use only the fixed native summary.
- Render proved lines separately from unknown coverage.
- Never infer open firmware status from history or an available update.
- Never wake a vehicle or run charging poll/control to complete the brief.
- This lookup and its output grant no runtime vehicle authority.
