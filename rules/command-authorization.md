---
alwaysApply: true
description: Controls run only from authorized chats, name the vehicle and action first, and report confirmed state
---

# Command Authorization

## Who May Control

- A control needs a chat protected host policy lists under `control_chats` or `owner_chats`
- Destination sharing requires an owner chat, including its preview
- A read-only chat can look at a vehicle and cannot change it
- The supported controls are the actions of `skills/tessie-ops/scripts/tessie-command.py`
- Wake, trunks, windows, remote start, honk, sentry, valet and the rest of Tessie's command list stay unsupported

## Name Before Acting

- Run `tessie-command.py` with `--dry-run` first and show the user the vehicle and action it prints
- Run the real command only after the user asks for that action on that vehicle
- Pass `--confirm` with the exact `<alias>:<action>` phrase from the plan
- Never pick a vehicle for the user when `selector_required` is reported

## Report What Happened

- Tessie's `result: true` means the command was accepted
- Say a control is done only when the status is `confirmed`
- Report `accepted` as sent without a state check, `unconfirmed` as not verified, and `failed` as refused
- Preserve accepted command details when the separate confirmation read fails
- Require state timestamps at or after actual host dispatch
- Never retry an unconfirmed or uncertain control on your own
- Never wake a vehicle to make a read fresher
