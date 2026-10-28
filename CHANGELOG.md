# Changelog

## 0.2.0 — 2026-10-28

### Add event-bound running-late delivery (#7)

Add a native-only three-minute consumer, owner-requested event approval cards and cancellation/status commands. The protected host rereads Calendar and cached navigation, uses a dedicated event-scoped Gmail grant, and reserves a hard shared two-message budget before each owner/recipient attempt. The host retains record2 native event identities; old unbound record1 state holds unchanged. Backup restores inactive gates without approval or slot reset. This source does not claim installed grants, actual route/cadence or outbound acceptance; issue7 remains open for native acceptance.

## 0.1.0 — 2026-10-26

### Add the script-first Tessie foundation (#1)

Ship the Tesla1 deterministic REST client, vehicle selection, protected chat/VIN policy, cached reads, common controls and quiet daily health precheck. Reuse the existing OneCLI gateway and vaulted Tessie API key; no additional credential, native actor or vault migration is required. The requested dynamic non-archived policy derives current active owner/shared vehicles from fresh inventory on each operation; no VIN snapshot or daemon substitutes for it. Production scripts call the native host broker, which derives registered source identity, validates fixed routes/parameters and filters non-owner location before replying. Agent-writable allowlists grant no control or location access.

Controls name the selected vehicle/action, persist a host intent before dispatch and require explicit confirmation. Tessie acceptance remains separate from matching post-dispatch state. Stale or failed confirmation preserves accepted receipts as unconfirmed; timeout/unknown outcomes never trigger automatic replay. Synthetic tests cover selection, permissions, transport errors, native IPC, command timing and acceptance preservation.

Package both skills, six rules, hashed development tools and real test CI. Enroll through the existing central GitHub review Apps, remove the unused per-repository PAT dispatcher, and opt into the canonical publisher's explicit out-of-credits carve-out. Threshold 85 and all non-credit failures remain required; every unreviewed skill is flagged and retried on the next publish. Source publication does not claim installed/native vehicle acceptance. Issue #1 stays open for that owner-authorized step; Tesla2–7 follow the foundation and Tesla8 stays held.

## 0.0.0 — 2026-10-26

### Added

- Establish the provider identity for reviewed Tesla overlay development, with a scoped namespace rule and central App enrollment.
- Add the pinned secret-scanning hook, generated-file exclusions and hook dependency renewal configuration.
