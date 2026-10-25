# Changelog

All notable changes to this plugin are documented here.

### Add the Tessie REST overlay foundation (#1)

The first release is the Tesla1 foundation that Tesla2–7 ([#2](https://github.com/jbaruch/nanoclaw-tesla/issues/2)–[#7](https://github.com/jbaruch/nanoclaw-tesla/issues/7)) compose; solar and Powerwall ([#8](https://github.com/jbaruch/nanoclaw-tesla/issues/8)) stay deferred.

- `skills/tessie-ops` ships six scripts over one client that talks only to `https://api.tessie.com` and sends no `Authorization` header: the OneCLI gateway injects the vaulted `Tessie API token` secret, query tokens and redirects are refused, and each call is a single attempt. Controls ask Tessie for `wait_for_completion=true` and `max_attempts` of at most 3 and add no retry loop.
- A default-deny allowlist at `/workspace/state/tessie-ops/allowlist.json` names addressable VINs and aliases. Tessie's live row must report `access_type` `OWNER` and `is_active` true unless the owner marks the entry `shared`. Discovery in an owner chat lists everything else with a `denied_reason` and no coordinates.
- Chat roles (`owner_chats`, `control_chats`, `read_chats`) come from the allowlist file, and the chat id is read from the container's init environment so a command-line `NANOCLAW_CHAT_JID` cannot grant location or controls. The allowlist lives in agent-writable state; `docs/setup.md` Hardening records that limit.
- Reads probe `GET /{vin}/status` and then use Tessie's cache. No wake action exists, no read sets `use_cache=false`, and a sleeping car answers with `from_cache` true. Coordinates, headings and street addresses are stripped unless an owner chat adds `--include-location`.
- Controls (lock, unlock, climate, temperature, charging, charge limit, share, flash, drive tag) need a `--dry-run` plan and a `--confirm "<alias>:<action>"` echo. Tessie's `result: true` reports as `accepted`; `confirmed` needs a cached state readback whose changed field matches and whose section timestamp is fresh; a mismatch or stale readback is `unconfirmed` (exit 3).
- `skills/tessie-watch` runs a daily precheck that wakes the agent only for a low unplugged battery, a script failure or unreadable state, and prints the `{wake_agent, data}` contract on its last line.
- Packaging and CI: plugin manifest, `tessl.json` floating `jbaruch/coding-policy`, hashed dev lock, Ruff, Pyright and pytest in `test.yml`, `publish.yml` calling the fleet publish pipeline, and the fleet review trigger. `.herdr/triggers.json` is the reviewed declaration, unchanged.
- Not verified until a native handshake: Tessie's error body shape and 429 headers, whether commands to a `waiting_for_sleep` car auto-wake, and how quickly Tessie's cache reflects a command (`docs/command-surface.md`).
