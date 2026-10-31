# Read-only vehicle morning summary

Contract: tessie-morning-brief-consumer-v1

Host owner: `jbaruch/nanoclaw` `src/host-plugins/tessie-brief/`. Read the full
installed `skills/host-contracts/references/tessie-morning-brief.md` before source
or runtime maintenance. `tessie_brief_request` is a separate schema1 fixed
`summary` operation, with no caller route/date/vehicle/role/enrollment fields.
The actual unique Telegram Main source and protected Tessie owner are required.
Current dynamic non-archived vehicles are resolved by the existing broker.
No consumer file, output, environment or successful estimate grants authority.

The fixed script loads the same-provider `tessie-charge/scripts/charge_ipc.py`,
which loads the co-shipped native `tessie-ops` transport. Installed prefixed skills
never search an unprefixed neighbor. Missing or incomplete closure refuses;
there is no direct HTTP or local policy fallback. One request is submitted,
with no automatic retry. The host owns cached Tessie reads, native home clock
and today's maintained drive metadata/energy estimation. It never wakes a car,
creates a command/notice intent, changes enrollment, registers a cadence or sends
a vehicle notice. IPC request/reply transport files are the sole consumer writes.

The script returns exact `{wake_agent:false,data}`. Data schema1 contains
`schema_version`, home `day`, `home_timezone`, UTC `observed_at`,
`checked_vehicles`, `coverage`, `uncovered_sources`, complete `vehicles`, and
literal deterministic `lines`. Each vehicle has exactly `alias`, `alerts` and
`unknown_checks`. Each alert has `kind` and the corresponding bounded detail
object described by `brief_ipc.py`. The script validates the full response
before emitting any line. It carries no VIN, precise location, saved-home label,
Calendar identity/body, credential or provider error prose.

One line combines every proved requested condition for one affected vehicle.
No line is emitted for a clear or unknown check. Stored overnight observations
are explicitly labelled as such; their bounded temporal coverage cannot prove
unobservable events between samples. Today-energy estimates remain conditional,
using the same measured capacity, consumption, allowances and forecast as #2.
Tire warnings name their positions. Current warning flags never mean that an
available software update is an alert.

Generic still-open firmware status is not exposed by the documented Tessie
history API. `uncovered_sources:["firmware_active_status"]` and partial coverage
remain explicit. Generated historical firmware entries are never relabelled
open. The supported positive current vehicle warning is the native cached
`not_enough_power_to_heat` flag. No new telemetry subscription, approval ledger
or persistent alert store exists. This capability limitation keeps the original
issue acceptance open; source tests do not establish complete firmware coverage.

Publish/install the Host contract, merge/deploy the real Core producer, then
publish this consumer and its optional Admin gather integration. The host checks
both declared installed provider contracts and complete regular transport files.
Missing/newer/unsupported contracts hold without a provider fallback. Root owns
native installed-byte, identity, asleep-cache/no-wake and normal-brief acceptance.
No live task, vehicle action or cadence is activated by this source release.

Schema1 admits a paired null `day`/`home_timezone` only for missing or invalid
protected native home. Both dependent checks remain unknown for every vehicle;
proved independent health lines survive. No fallback timezone is supplied.
Half-null or falsely complete dependent coverage refuses. Host data remains
bounded at 128 KiB; the complete fixed rendered envelope is bounded at 256 KiB.

Brief aliases are nonempty and bounded at 100 UTF-16 code units (at most
300 UTF-8 bytes), matching native admission and the saved reader. Oversized or
unsafe upstream aliases hold the complete summary; never truncate or drop a
vehicle. Brief-only VIN-free ordinal labels do not change native selectors.


## Scoped consumer lookup

`rules/vehicle-brief-policy.md` declares the fixed executable and pure validator
interfaces. The native skill projection and existing read-only per-provider
projection must belong to the same `jbaruch/nanoclaw-tesla` manifest, declared
rule and skill. Verify contained regular metadata, authority/reference and every
fixed transport target; reject provider substitution, links, changed copies or
an in-progress projection update before execution/import and after readback.
An absent old overlay is unavailable; present unsupported or incomplete provider
material is an error, never healthy evidence. No caller root or fallback target
selects this source. Native Main and protected-owner checks remain in Core.


## Capture-bound call

The declared `skills/tessie-brief/scripts/brief_ipc.py — call()` accepts the
optional keyword-only `expected_source_hashes=None`. With no inventory, the
ordinary fixed CLI and call retain their existing behavior and output. A supplied
inventory is an additional refusal precondition, never a provider selector,
identity, approval, freshness attestation or vehicle grant. It changes no native
payload, route, output schema, CLI argument, store or cadence.

Supply a plain dictionary containing exactly these paths, each mapped to its
lowercase SHA-256 hex digest from the consumer's one verified initial capture:

- `.tessl-plugin/plugin.json`
- `rules/vehicle-brief-policy.md`
- `skills/tessie-brief/references/host-contract.md`
- `skills/tessie-brief/SKILL.md`
- `skills/tessie-brief/scripts/tessie-brief.py`
- `skills/tessie-brief/scripts/brief_ipc.py`
- `skills/tessie-charge/scripts/charge_ipc.py`
- `skills/tessie-ops/scripts/tessie_native.py`
- `skills/tessie-ops/scripts/tessie_core.py`

The provider owns an immutable copy. Missing, extra or malformed entries and any
source mismatch raise `ValueError` before transport compilation or IPC. Every
existing constructor, call and readback fence checks the same inventory again.
The five native code copies still must byte-match their provider, and transport
execution uses the provider's verified captured bytes. A concurrent matching
provider/native replacement cannot change which code the initial capture permits.
Preserve every live filesystem identity, containment and attachment check; hashes
do not replace those checks or authorize a retry after an uncertain result.

An Admin consumer may execute the captured complete CLI and brief module with a
private literal `brief_ipc` import facade that delegates only to this public call
with the initial inventory. It must not rebind private provider classes or global
module/import registries. Install and read this declared provider contract before
using the optional handoff; an older provider without the declaration is held.
