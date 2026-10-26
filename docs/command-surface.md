# Command Surface

What the `tessie-ops` scripts support, what they refuse, and the vehicle limits to expect. Every script, flag and exit code lives in the script's own docstring; this page records the supported surface and the evidence behind it.

## Reads

| Script call | Tessie endpoint | Who may run it |
| --- | --- | --- |
| `tessie-vehicles.py` | `GET /vehicles` | any role |
| `tessie-read.py status` | `GET /{vin}/status` | any role |
| `tessie-read.py state` | `GET /{vin}/state` | any role |
| `tessie-read.py battery` | `GET /{vin}/battery` | any role |
| `tessie-read.py tire_pressure` | `GET /{vin}/tire_pressure` | any role |
| `tessie-read.py firmware_alerts` | `GET /{vin}/firmware_alerts` | any role |
| `tessie-read.py consumption_since_charge` | `GET /{vin}/consumption_since_charge` | any role |
| `tessie-read.py last_idle_state` | `GET /{vin}/last_idle_state` | any role |
| `tessie-read.py drives` | `GET /{vin}/drives` | any role |
| `tessie-read.py location --include-location` | `GET /{vin}/location` | owner chats |
| `tessie-read.py drivers` | `GET /{vin}/drivers` | owner chats |

- Every read probes `status` first, then reads Tessie's cached copy. A sleeping car reports `vehicle_status` `asleep` or `waiting_for_sleep` and `from_cache` true
- No read calls wake and none asks for a live read
- Coordinates, headings and street addresses are stripped unless an owner chat adds `--include-location`. Saved location names pass

## Controls

| Action | Tessie endpoint | Parameters | State readback |
| --- | --- | --- | --- |
| `lock` / `unlock` | `POST /{vin}/command/lock`, `unlock` | none | `vehicle_state.locked` |
| `start_climate` / `stop_climate` | `POST /{vin}/command/start_climate`, `stop_climate` | none | `climate_state.is_climate_on` |
| `set_temperatures` | `POST /{vin}/command/set_temperatures` | `temperature` °C | `climate_state.driver_temp_setting` |
| `start_charging` / `stop_charging` | `POST /{vin}/command/start_charging`, `stop_charging` | none | `charge_state.charging_state` |
| `set_charge_limit` | `POST /{vin}/command/set_charge_limit` | `percent` | `charge_state.charge_limit_soc` |
| `share` | `POST /{vin}/command/share` | `value`, optional `locale` | none: acceptance only |
| `flash` | `POST /{vin}/command/flash` | none | none: acceptance only |
| `set_drive_tag` | `POST /{vin}/drives/set_tag` | `drives`, optional `tag` | none: not a vehicle actuator |

- Controls need a control or owner chat, the allowlist, a `--dry-run` plan and a `--confirm "<alias>:<action>"` echo
- Each control sends once with `wait_for_completion=true` and `max_attempts` at most 3; the client adds no retry
- Outcomes: `confirmed`, `accepted`, `unconfirmed` (exit 3), `failed` (exit 1). Tessie's `{"result": true}` is acceptance. `confirmed` needs a cached state read whose changed field matches and whose valid section timestamp is at least the command send time; a matching pre-command state never confirms. If the separate readback fails, the result retains the accepted command receipt with `status: unconfirmed`, safe error category metadata and a no-automatic-retry diagnostic
- Tessie documents automatic wake-up and firmware-error handling for controls, so a control may wake a sleeping car even though the overlay never calls wake

## Unsupported

Wake, trunks, windows, sunroof, homelink, keyless driving and remote start, boombox, honk, sentry, valet, speed limit and PIN, guest mode, driver and invitation management, telemetry config, software update, scheduled charging and precondition writers, seat and steering-wheel climate, charging amps and charge port, and every energy-site or Powerwall call.

- The overlay exposes none of these. A script argument for one is rejected before any request
- Tessie's Fleet API passthrough (`api.tessie.com/api/1/...`, same token) remains the documented path for true Tessie API gaps and for solar/Powerwall work; neither is built here

## Vehicle limits

- Field presence differs by model. Live inventory on 2026-10-25 showed `lychee` and `cybertruck` vehicles; fixtures cover both shapes and the scripts read fields defensively
- Read `vehicle_config` from `tessie-read.py state` before assuming a capability: `can_accept_navigation_requests` (share), `can_actuate_trunks`, `has_seat_cooling`, `motorized_charge_port`
- Tire pressure needs vehicle firmware 2022.4.5 or newer
- `access_type` is an unenumerated string in Tessie's schema; the host recognizes OWNER and DRIVER for dynamic non-archived selection, and refuses unknown access

## Unverified until a native handshake

These behaviors are hypothesized from the public reference and stay unproven until the post-install smoke records them:

- the JSON shape of Tessie error bodies and the headers of a 429
- whether a command to a `waiting_for_sleep` car still auto-wakes it
- field differences between `lychee`, `tamarind` and other `car_type` values
- whether an inactive `DRIVER` vehicle accepts commands (the requested dynamic non-archived mode excludes it)
- whether Tessie's cached state reflects a command immediately, which decides how often `unconfirmed` appears for a command that worked
