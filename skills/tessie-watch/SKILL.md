---
name: tessie-watch
description: "Daily vehicle health watch for the Tessie overlay: wakes only when an addressable vehicle has a low unplugged battery, a Tessie credential or API failure, or unreadable state, then tells the owner what was found; otherwise stays silent. Triggers: 'tesla watch', 'vehicle health check', 'tessie watch', 'monitor my Tesla', 'low battery alert'."
cadence: "0 7 * * * (TZ=local)"
script: "scripts/tessie-precheck.py"
---

# Tessie Watch

Process steps in order. Do not skip ahead.

The fire-time precheck (`scripts/tessie-precheck.py`) reads every addressable vehicle from Tessie's cache and wakes the agent only when something needs attention. Its thresholds, wake conditions and output shape are the script's contract (top-of-file docstring and constants). This skill is the foundation check; Tesla2-7 features compose the `tessie-ops` scripts and bring their own prechecks.

## Step 1 — Report The Alert

The wake data names a `reason` and, for `attention_needed`, an `alerts` list. If the data carries no alert and no failure, finish silently.

State each fact as a declarative sentence in the chat's language: which vehicle (alias), what the precheck found, and what the owner can do. For `low_battery_unplugged`, add the battery level and say it is not plugged in. For `script_failed`, `script_timeout`, `bad_output` or `precheck_error`, quote the `error` text and point to `docs/setup.md` Recovery. Never include coordinates or addresses. Never ask whether the owner already knows.

Send the message with `mcp__nanoclaw__send_message` and finish here. Do not run controls: a notice grants no authority to act on the vehicle.
