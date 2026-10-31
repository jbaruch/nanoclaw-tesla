---
name: tessie-brief
description: "Read a deterministic vehicle summary for the morning brief or an owner request: proven overnight unplugged observations, today's measured drive shortfall, positional tire warnings and supported current vehicle warnings. Triggers: 'vehicle morning brief', 'car issues today', 'Tesla brief', 'машины утром'. Cached reads only; no vehicle wake or controls."
---

# Vehicle Brief

Process steps in order. Do not skip ahead.

## Step 1 — Read the source contract

Read the complete contract before interpreting the result:

`skills/tessie-brief/references/host-contract.md`

It defines the supported evidence and missing coverage. Source publication is not
native deployment, health proof, enrollment or permission for a vehicle effect.
Proceed immediately to Step 2.

## Step 2 — Collect the summary

```bash
python3 /home/node/.claude/skills/tessl__tessie-brief/scripts/tessie-brief.py
```

No arguments. The docstring of `skills/tessie-brief/scripts/tessie-brief.py`
owns its input, output and exit contract. Exit 0 returns `wake_agent:false` and schema1 `data`
with deterministic `lines`, observed home day and separate incomplete coverage.
No poll, control, notice, task, vehicle wake or authority write occurs.
After valid successful output, proceed immediately to Step 3.

Exit 1 has fixed stderr and no stdout. Nonzero or invalid output: report the fixed diagnostic and stop. Never call a
vehicle wake, bypass the cache or run charging poll to complete this summary.

## Step 3 — Use only proved lines

Include each returned line once, without adding a vehicle condition. The morning
brief owns its transport; this skill sends no separate notice. For a standalone
owner request, state the returned lines and missing coverage plainly. Empty
lines with partial coverage means no proved alert, not that all cars are healthy.
Keep unknown checks separate from proved lines; never infer open firmware alerts
from history or an available software update. Finish here.
