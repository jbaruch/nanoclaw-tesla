# Setup

How to connect the `nanoclaw-tesla` overlay to Tessie, authorize vehicles and chats, verify the install, revoke access and recover from failures. This repository ships the plugin; the allowlist contents, the chat that loads the overlay and the install itself are owner decisions made on the NanoClaw host.

## 1. Tessie access token

- Create the token at <https://dash.tessie.com/settings/api>. Tessie authenticates with one access token sent as `Authorization: Bearer <token>`
- Store it only in the OneCLI vault as the secret named `Tessie API token`: type `generic`, host pattern `api.tessie.com`, header `Authorization`
- The vault secret for this NanoClaw already exists (id `5269dc31-7972-4197-854c-0601e8354b1a`, created 2026-10-21). Reuse it; request no second token
- The OneCLI gateway injects the header on the wire. The scripts send no `Authorization` header and refuse token query parameters, so the token never reaches a container, a log or the chat
- Never put the token in `.env`, `.env.example`, a compose file or this repository

## 2. Vehicle allowlist

Default deny: with no allowlist file, no vehicle is addressable and every script exits 4.

Create `/workspace/state/tessie-ops/allowlist.json` (mode 0600, owned by the agent identity):

```json
{
  "schema_version": 1,
  "default_vehicle": "The Rustler",
  "owner_chats": ["<chat id of your private owner chat>"],
  "control_chats": [],
  "read_chats": [],
  "watch": {"low_battery_percent": 20},
  "vehicles": [
    {"vin": "<17-character VIN>", "alias": "The Rustler"},
    {"vin": "<17-character VIN>", "alias": "Bradbury"}
  ]
}
```

- A vehicle is addressable when its VIN is listed and Tessie's live row reports `access_type` `OWNER` and `is_active` true
- Vehicles other owners shared with the account (`DRIVER`, `null` access, inactive) stay excluded. Set `"shared": true` on a listed entry only when you want a non-owner vehicle addressable
- `default_vehicle` is optional; with two addressable vehicles and no default, scripts ask for `--vehicle`
- `owner_chats` may read, control and see precise location; `control_chats` may read and control; `read_chats` may read non-location data. A chat in no list is denied everything
- The chat id is the registered chat's `NANOCLAW_CHAT_JID` value, as the host provides it to that chat's container
- `watch.low_battery_percent` is optional; the daily `tessie-watch` check uses it (default in `skills/tessie-watch/scripts/tessie-precheck.py`)

Check it from an authorized chat:

```bash
python3 /home/node/.claude/skills/tessl__tessie-ops/scripts/tessie-allowlist.py show
python3 /home/node/.claude/skills/tessl__tessie-ops/scripts/tessie-vehicles.py --include-denied
```

### Hardening

- The scripts treat the allowlist as read-only owner configuration. It sits in `/workspace/state`, which every container can write, so an agent that can run shell commands can edit its own authorization file
- Chat identity is read from the container's init environment, which a command line cannot override. The roles it selects still come from this file
- Keep the file owner-managed on the host and mount it read-only where your NanoClaw deployment allows. Until then, treat control and location authorization as only as strong as that mount

## 3. Load the overlay on a chat

- The overlay loads per chat through `containerConfig.additionalTiles` with the bare name `nanoclaw-tesla`
- NanoClaw's `manage-groups` refuses `set_additional_tiles` on the main chat, so use an owner chat that is not main, then nuke that chat so it picks the overlay up
- Install the published plugin on the NAS with `tessl` before that. A merged pull request is not an installed plugin

## 4. Verify

From a read-capable chat:

1. `tessie-vehicles.py` lists your allowlisted vehicles by alias and VIN suffix
2. `tessie-read.py state --vehicle "<alias>"` returns `vehicle_status` and cached data; on a sleeping car `from_cache` is true and nothing wakes it
3. `tessie-command.py lock --vehicle "<alias>" --dry-run` prints the plan and sends nothing

A live control test is a separate owner-authorized step: pick the vehicle, send a reversible command only when status is `awake`, and read the state back.

## 5. Revoke

- Delete the token at <https://dash.tessie.com/settings/api>. Every script then exits 1 with an HTTP 401 diagnostic
- Remove the `Tessie API token` secret from the OneCLI vault
- Remove a vehicle from the allowlist to stop addressing it, or remove the whole file to deny everything

## 6. Recovery

| Symptom | Meaning | Fix |
| --- | --- | --- |
| exit 4, `allowlist_missing` | no allowlist file | create it as in section 2 |
| exit 4, `chat_unauthorized` | chat id is in no list | add it to `owner_chats`, `control_chats` or `read_chats` |
| exit 4, `chat_unwitnessed` | the host chat id could not be read from the init environment | report it; controls and location stay denied |
| exit 4, `not_owner_access` or `inactive` | Tessie reports the vehicle as shared or inactive | fix access in the Tessie app, or set `shared` deliberately |
| HTTP 401 | token missing, expired or revoked | create a new token, update the vault secret |
| HTTP 403 | token cannot reach the vehicle | check the vehicle's access in the Tessie app |
| HTTP 404 | vehicle gone from the account | re-run `tessie-vehicles.py --include-denied` |
| HTTP 408 | Tessie timed out reaching the car | read cached status; do not loop |
| HTTP 429 | rate limit | stop; the diagnostic carries `Retry-After` when Tessie sends it |
| HTTP 5xx | Tessie failed upstream | try again later; no retry is attempted |
| control `unconfirmed` | Tessie accepted it; fresh state does not show the change | read state again later; do not report it as done |

## Usage limits and cost

- Tessie's published API reference (OpenAPI, 2026-10-25) lists success responses only: no error schemas, no rate limits and no price table. This repository states no figure it could not verify
- Check <https://tessie.com> for current plan and API terms before relying on volume
- Call budget per operation, so a plan's quota can be sized: a read is three requests (`/vehicles`, `/status`, the data endpoint); a control is three (`/vehicles`, the command, `/state`); `tessie-vehicles.py` is one
- The daily `tessie-watch` check costs 1 request plus 3 per addressable vehicle
- Reads never ask Tessie for a live (`use_cache=false`) copy and never wake a vehicle. Tessie may wake a sleeping car to run a control; see `docs/command-surface.md`
