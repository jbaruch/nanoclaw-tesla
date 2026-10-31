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
