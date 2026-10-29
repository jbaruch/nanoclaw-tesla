# Native calendar charging

Contract: tessie-calendar-charge-consumer-v2

The protected Core owner is `src/host-plugins/tessie-charge/`, sharing the existing
Tessie broker, OneCLI route, dynamic non-archived inventory and private
`DATA_DIR/tessie-authority` store. The installed Host authority is the complete
`skills/host-contracts/references/tessie-calendar-charge.md` reference in
`jbaruch/nanoclaw-host`. Read it before enrollment or host maintenance. No callback
database migration, new credential or consumer authority store exists.

## Admission and planning

The host requires the actual unique registered Telegram main source and a
protected owner enrollment. Policy 2 stays readable without charging authority; policy 3 adds
nullable `charge_automation`. Only the host operator provisions it from an actual
owner decision after installing the dual reader. Caller flags, JSON, task IDs,
local files and successful estimates cannot grant enrollment or control.
Current nested enrollment is schema2 with required `home_timezone`; top-level
policy remains3. Legacy nested enrollment1 is readable only for basic Tessie
policy compatibility; it grants no charging action authority. Planning and
controls hold with `charge_enrollment_version`. No consumer supplies or migrates that authority.

Enrollment selects an optional default vehicle, exact event/driver mappings,
native home labels, home-zone evening hour, daily baseline expectation and energy
buffers. No VIN allowlist is snapshotted. The broker rereads current non-archived
vehicles and existing authorization before a control. Baselines outside the
authorized 50–100 range hold; never clamp them or make restoration unauthorized.

Charging uses only the native host's supported schema-4 `tz_state.home_tz`.
The bound `home_timezone` must be a trimmed nonempty valid IANA string of at most
100 UTF-16 code units. Missing, unsupported or invalid home
state holds; travel/current timezone, agent context, server timezone and UTC
are not fallbacks. Today/tomorrow, day boundaries, evening admission and notice
budgets all use this home clock. A changed home must hold at the existing
runtime recheck before an effect. Enrollment2 `home_timezone` must match native
home at every fence; current charge-state2 and charge-notice2 carry that same
required IANA binding. Native request/response wire1 remains unchanged.

Before planning effects or a new notice-day lookup, the host performs bounded
ALL-notice discovery alongside complete charge-state discovery. Legacy state1
and notice1, including a notice saved under another day, hold byte-exact with
`charge_state_version` or `charge_notice_version`. Unknown/future/malformed or
misbound records hold rather than becoming absence. No automatic migration,
rekey, retag, reset, guessed timezone or reopened notice slot is permitted.

Only maintained drive-engine schema-1 Calendar metadata identifies drives; titles
and city substrings supply no evidence. The host reads complete bounded next-day
pages and retains original native event IDs across long trips. It rereads those
IDs independently of the current day query. An exact native cancelled record or fixed event GET returning HTTP 410 with the
documented single global/deleted reason supplies cancellation evidence; missing/inaccessible IDs or conflicting revisions
hold, rather than appearing cancelled.

Fixed normal main OneCLI Calendar/Maps reads and the Tessie broker supply measured
capacity, recent driving consumption, route distance and bounded-age charging/home
observations. No raw Maps/Tessie keys enter scripts. Cached reads never wake a
vehicle. Energy includes explicit cold/highway allowances and reserve; rated range
never replaces measurements. Estimates expose no precise location or Calendar body.

## Effects and uncertainty

In the enrolled evening in the home zone, raise only for the measured shortfall
on the next home calendar day, up to 100.
A disconnected shortfall gets at most one owner notice. A route beyond usable
charge includes minimum energy charging stops, not a charger itinerary. After
completed drives and native return-home proof, or exact native cancellation,
restore the original daily baseline silently.

The host persists a private charge gate before its command intent and one POST.
Fresh native policy, source, inventory and actual observed limit are rechecked.
An observed external limit change becomes a sticky owner-override hold, as does a
host-observed manual limit command, including A→B→A. Tessie
offers no compare-and-set parameter: changes after the last cached read, including
ABA changes, are unobservable. Do not promise absolute override protection. The
owner must accept that limitation before native enrollment.

Acceptance is not confirmation. Preserve accepted intent until matching native
state at/after dispatch confirms the limit. Matching read-only recovery can settle
an accepted unconfirmed request without another POST. A failed/unknown command
remains held; no consumer retry, reset, erase or re-enrollment path exists. Only a
broker-persisted witness that its provider POST was never entered permits the
host to restore the exact pre-attempt charge checkpoint under still-current
authority, then replan from fresh facts with a new request identity. The entire
current charge record/operation must still match; revocation, changed enrollment
or a sticky manual override prevents restoration. The host never rolls policy
back or removes the original command tombstone. Provider refusal after dispatch
is not proof of no effect and does not gain this recovery.

The host reserves one bounded Russian owner notice per home-zone evening before send.
Crash/timeout consumes that slot. Submitted is a resolved native send call, not a
channel acknowledgment. Long fleets receive an honest aggregate; every structured
item remains in the native result. No model-generated duplicate follows the poll.

## Wire and source rollout

The same-provider `charge_ipc.py` loads co-shipped `tessie_native.py` and
`tessie_core.py`. It sends one `tessie_charge_request` schema 1 through existing
native IPC with a 200-second reply wait. No direct HTTP or role fallback exists.
Operations are `poll`, `status` and read-only `estimate` with exact vehicle,
distance_km and zoned departure fields. Status performs no provider operation;
estimate grants no control or notice. Missing host/contract/enrollment stays held.

The precheck is an executable adapter for a later explicitly registered cadence.
It emits `wake_agent:false` and counts after success; failures retain nonzero plus
a fixed repair diagnostic. No cadence frontmatter enrolls it automatically.
The host operator pins the separately authorized cadence to the verified home
IANA timezone, never `schedule_timezone: local`, which follows travel. Verify its
next run at the enrolled home wall time before activation and reverify after a
native home change. This is registration guidance, not a consumer scheduler or
permission to create another cadence.

For this contract-only v2 bootstrap, publish/install matching
`tessie-calendar-charge-host-v2` and this consumer-v2 contract first. Python
runtime and wire1 remain unchanged; incumbent Core v1 contract checks hold v2,
and charging stays unenrolled with no cadence. Then merge/install the compatible
Core v2 reader. Other producer/consumer releases retain the normal producer-first
order in the Host authority.

After compatible readers are installed and native identity/home/policy bindings
are verified, the host operator provisions a new schema2 enrollment epoch from
an actual owner decision. Live-effect acceptance remains separately approved;
the decision need not be reissued after installation. All matching contracts
and the compatible Core reader must be installed before any schema2 writer.
Legacy charging/gates remain held. A clean current native store is not a general
legacy-schema exception.
The host checks declared installed providers and complete regular
co-shipped files before dispatch. Source release proves no native enrollment,
vehicle effect, real clock/cadence, route, channel acknowledgment or owner decision.
Keep issue #2 open until the host operator completes those native acceptance checks.
