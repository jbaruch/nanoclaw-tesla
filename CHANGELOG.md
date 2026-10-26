# Changelog

### Add the script-first Tessie foundation (#1)

Ship the Tesla1 deterministic REST client, vehicle selection, protected chat/VIN policy, cached reads, common controls and quiet daily health precheck. Reuse the existing OneCLI gateway and vaulted Tessie API key; no additional credential, native actor or vault migration is required. Production scripts call the native host broker, which derives registered source identity, validates fixed routes/parameters and filters non-owner location before replying. Agent-writable allowlists grant no control or location access.

Controls name the selected vehicle/action, persist a host intent before dispatch and require explicit confirmation. Tessie acceptance remains separate from matching post-dispatch state. Stale or failed confirmation preserves accepted receipts as unconfirmed; timeout/unknown outcomes never trigger automatic replay. Synthetic tests cover selection, permissions, transport errors, native IPC, command timing and acceptance preservation.

Package both skills, five rules, hashed development tools and real test CI. Enroll through the existing central GitHub review Apps, remove the unused per-repository PAT dispatcher, and opt into the canonical publisher's explicit out-of-credits carve-out. Threshold 85 and all non-credit failures remain required; every unreviewed skill is flagged and retried on the next publish. Source publication does not claim installed/native vehicle acceptance. Issue #1 stays open for that owner-authorized step; Tesla2–7 follow the foundation and Tesla8 stays held.
