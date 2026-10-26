# Setup

The native host owns authorization and provider access. Install the published host
Tessie authority and its matching `jbaruch/nanoclaw` producer before enabling this
overlay. Source delivery does not claim installation or live vehicle acceptance.

## Protected host policy

The host owner provisions `DATA_DIR/tessie-authority` as a real host-owned `0700`
directory, with an empty host-owned `.agent-empty` directory at `0555`. NanoClaw
masks the entire private directory from agent mounts and project aliases even
when the broker is disabled. Unsafe existing storage blocks agent startup.

The host owner creates `policy.json` at `0600`, with this schema. The empty
example authorizes nobody; use actual existing native chat/VIN IDs
only during the separately authorized owner provisioning step.

```json
{
  "schema_version": 2,
  "vehicle_selection": "non_archived",
  "owner_chats": [],
  "control_chats": [],
  "read_chats": [],
  "vehicles": [],
  "default_vehicle": null,
  "low_battery_percent": 20
}
```

The requested `non_archived` mode is dynamic: keep protected `vehicles` empty and
`default_vehicle` null. Every new operation derives the current list from fresh
Tessie inventory with actual `is_active: true` and recognized native OWNER or
DRIVER access. Active shared vehicles are included by this explicit owner opt-in;
archived vehicles are excluded. New or unarchived vehicles appear on the next
request without editing policy. Unknown access never grants authority.

Aliases use current native display names, a stable VIN fallback for unnamed
vehicles, and deterministic VIN disambiguation for duplicates. A rename requires
the current exact alias in control confirmation. A completed receipt is historical
readback and remains readable without provider I/O; it sends no new command.

Optional `explicit` selection retains individually protected entries with exactly
`vin`, normalized `alias`, and boolean `shared`, plus a listed default alias or
null. Non-shared entries require current OWNER/active proof; explicit shared
entries still require live presence. This static mode does not implement the
owner's requested dynamic list. Unsupported protected policy versions refuse
with an owner-repair diagnostic; agents never migrate or rewrite the private file.

Owner chats may read precise location and drivers. Control chats may read the
host's non-location projection and control listed vehicles. Read chats cannot
control. Source-group registration determines the native chat identity; flags,
conversation claims, process variables and agent-writable files grant nothing.
The scripts' additional init-environment witness can refuse a request but cannot
grant access the host denies. Legacy scratch allowlists are not production inputs.

The host projects top-level `low_battery_percent` into
`watch.low_battery_percent` in the own-role IPC response. `tessie-allowlist.py show`
exposes that client shape to the watch precheck. The precheck retains per-vehicle
errors alongside battery alerts and continues checking every listed vehicle.

## Existing OneCLI credential proxy

Reuse the existing OneCLI-vaulted generic Tessie API key for `api.tessie.com`.
The normal OneCLI gateway injects its `Authorization` header. The host broker
uses that existing route; scripts use native IPC. Key values never enter
container files, host request bodies, logs or chat. No additional Tessie token,
OneCLI identity, grant migration or credential provisioning variable is needed
when this key and gateway are already configured.

For a new installation only, the host owner creates a Tessie token at
<https://dash.tessie.com/settings/api> and stores it in OneCLI as a generic
secret for `api.tessie.com`, header `Authorization`. Never paste its value into
chat or this repository. Preserve the existing configured key on this system.

The host owner provisions the requested protected VIN/chat policy, enables the
default-disabled domain feature (`TESSIE_ENABLED=true`), and deploys the reviewed
producer through the canonical NanoClaw workflow. Missing gateway configuration
fails without direct HTTP fallback. This source task performs no deployment,
provider call, browser action, grant change or vehicle operation.

## Overlay installation

Install the published plugin with Tessl and load bare overlay name
`nanoclaw-tesla` through an authorized non-main chat's
`containerConfig.additionalTiles`. Restart that chat through the canonical host
workflow after installation. Preserve the actual registered native chat IDs.
A merged PR or synthetic test is not proof of an installed producer/consumer.

## Command and failure semantics

Scripts emit a plan before controls and require `--confirm "<alias>:<action>"`.
The host independently checks role, VIN, current live access, fixed route,
parameters and the selected alias/action. It never exposes raw provider errors,
credentials, proxy configuration or unknown response fields to non-owner chats.

Before POST dispatch the host fsyncs a private command intent. The same native
request ID cannot replay a timed-out, torn or unknown command after restart.
Duplicate completed requests retain their prior accepted/refused receipt.
Commands have no automatic retry loop; Tessie's own bounded `max_attempts` is
explicit. An IPC timeout may mean the command was sent. Inspect cached state;
do not resend it automatically or report definite non-application.

`result: true` is acceptance. `confirmed` requires matching state whose timestamp
is at or after actual host dispatch, with no pre-command grace period. A stale,
mismatched or failed readback retains the accepted receipt and returns
`unconfirmed` with exit 3. Missing host dispatch proof also remains unconfirmed.
Flash, share and drive tags report acceptance without state confirmation.

| Failure | Required response |
| --- | --- |
| exit 4 / native contract or policy unavailable | Owner inspects installed contract, registration, protected policy and existing gateway; do not create scratch grants |
| HTTP 401 | Owner repairs the existing vaulted credential; never request a duplicate token in chat |
| HTTP 403/404 | Owner verifies account/vehicle access; cached inventory may have changed |
| HTTP 408/429/5xx | Stop; inspect status or wait for an explicit later request; no looping |
| timeout / uncertain / unconfirmed | Keep known acceptance, read cached state, never automatically replay |

Revocation removes the protected VIN/chat entry, disables the broker, or revokes
the existing vault credential. Preserve command intents while resolving uncertain
operations. No retention/erasure action is implicit in this setup guide.

## Live acceptance and cost

The host owner separately verifies installed producer/consumer bytes, actual
role denial, cached sleeping-car reads and one explicitly authorized reversible
control on a selected awake vehicle. Verify fresh post-command state and no
location outside the owner chat. Confirm the daily `tessie-watch` cadence row in
native `scheduled_tasks`. Until those checks pass, issue #1 remains open.

Tessie pricing, account quota and Fleet passthrough availability depend on the
current plan. Consult the [official API index](https://developer.tessie.com/llms.txt)
and account terms before enabling scheduled volume. No unverified price or quota
is assumed. The fixed foundation routes do not require arbitrary Fleet passthrough.

The broker rechecks live inventory before each vehicle request. One vehicle list
uses one Tessie call; a normal state read or state-confirmed command uses five.
The gateway owns credential injection for every provider request.
A daily watch composes the scripts and multiplies that budget by admitted vehicles.
Reads keep default cached behavior; no wake or `use_cache=false` route is allowed.
