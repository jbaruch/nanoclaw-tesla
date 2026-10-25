"""Vehicle allowlist, chat authorization and vehicle selection for tessie-ops.

Default deny. A vehicle is addressable only when ALL of these hold:

1. its VIN is listed in the allowlist file (`ALLOWLIST_PATH`);
2. Tessie's live inventory reports `access_type == "OWNER"` and `is_active is true`,
   unless the owner set `"shared": true` on that listed VIN;
3. the calling chat holds a role that permits the operation.

Chat identity is witnessed, not claimed. `NANOCLAW_CHAT_JID` is passed by the
host as a container `-e` variable, so it lives in the init process
environment (`WITNESS_ENVIRON_PATH`), which an agent cannot rewrite from a
command line the way it can rewrite its own process environment. The witness
read wins; a process-environment value that disagrees with it is a refusal,
and an unreadable witness denies everything.

Roles come from the owner-written allowlist file, never from a flag:

- `owner_chats`   — reads, controls, precise location, drivers list
- `control_chats` — non-location reads and controls
- `read_chats`    — non-location reads

Allowlist file (schema_version 1) at `/workspace/state/tessie-ops/allowlist.json`:

    {
      "schema_version": 1,
      "default_vehicle": "The Rustler",            (optional alias)
      "owner_chats": ["tg:-100..."],
      "control_chats": [],
      "read_chats": [],
      "watch": {"low_battery_percent": 20},        (optional)
      "vehicles": [{"vin": "...", "alias": "The Rustler", "shared": false}]
    }

The file is owner configuration, read-only to every script here. It lives in
agent-writable state, so it is only as trustworthy as that mount (see
docs/setup.md, Hardening).
"""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tessie_core import EXIT_DENIED, VIN_PATTERN, TessieError

ALLOWLIST_PATH = Path("/workspace/state/tessie-ops/allowlist.json")
WITNESS_ENVIRON_PATH = Path("/proc/1/environ")
CHAT_JID_ENV = "NANOCLAW_CHAT_JID"
SUPPORTED_ALLOWLIST_SCHEMA = 1

ROLE_READ = "read"
ROLE_CONTROL = "control"
ROLE_OWNER = "owner"
_ROLE_RANK = {ROLE_READ: 1, ROLE_CONTROL: 2, ROLE_OWNER: 3}

# Denied reasons surfaced to the owner chat; stable strings Tesla2-7 can match.
DENIED_NOT_ALLOWLISTED = "not_allowlisted"
DENIED_UNKNOWN_ALIAS = "unknown_alias"
DENIED_NOT_OWNER_ACCESS = "not_owner_access"
DENIED_INACTIVE = "inactive"
DENIED_NOT_IN_INVENTORY = "not_in_live_inventory"
SELECTOR_REQUIRED = "selector_required"


@dataclass(frozen=True)
class AllowedVehicle:
    vin: str
    alias: str
    shared: bool


@dataclass(frozen=True)
class Allowlist:
    vehicles: tuple[AllowedVehicle, ...]
    default_vehicle: str | None
    owner_chats: frozenset[str]
    control_chats: frozenset[str]
    read_chats: frozenset[str]
    low_battery_percent: int | None


@dataclass(frozen=True)
class LiveVehicle:
    vin: str
    access_type: str | None
    is_active: bool | None
    display_name: str | None
    car_type: str | None


@dataclass(frozen=True)
class ResolvedVehicle:
    vin: str
    alias: str
    vin_suffix: str
    live: LiveVehicle


def _denied(message: str, code: str) -> TessieError:
    return TessieError(message, code=code, exit_code=EXIT_DENIED)


def norm_alias(value: str) -> str:
    return " ".join(value.split()).casefold()


def vin_suffix(vin: str) -> str:
    return vin[-4:]


# --- Allowlist file -----------------------------------------------------------


def _chat_set(raw: Mapping[str, Any], key: str) -> frozenset[str]:
    value = raw.get(key, [])
    if not isinstance(value, list) or not all(isinstance(i, str) and i for i in value):
        raise _denied(
            f"allowlist {key!r} must be a list of non-empty chat ids (docs/setup.md)",
            "allowlist_invalid",
        )
    return frozenset(value)


def _parse_vehicle(raw: object, index: int) -> AllowedVehicle:
    if not isinstance(raw, dict):
        raise _denied(f"allowlist vehicles[{index}] must be an object", "allowlist_invalid")
    vin = raw.get("vin")
    alias = raw.get("alias")
    shared = raw.get("shared", False)
    if not isinstance(vin, str) or not VIN_PATTERN.match(vin.upper()):
        raise _denied(
            f"allowlist vehicles[{index}].vin must be a 17-character VIN", "allowlist_invalid"
        )
    if not isinstance(alias, str) or not alias.strip():
        raise _denied(
            f"allowlist vehicles[{index}].alias must be a non-empty string", "allowlist_invalid"
        )
    if not isinstance(shared, bool):
        raise _denied(
            f"allowlist vehicles[{index}].shared must be true or false", "allowlist_invalid"
        )
    return AllowedVehicle(vin=vin.upper(), alias=" ".join(alias.split()), shared=shared)


def parse_allowlist(raw: object) -> Allowlist:
    if not isinstance(raw, dict):
        raise _denied("allowlist root must be a JSON object", "allowlist_invalid")
    schema = raw.get("schema_version")
    if schema != SUPPORTED_ALLOWLIST_SCHEMA or isinstance(schema, bool):
        raise _denied(
            f"allowlist schema_version={schema!r} is not supported (expected "
            f"{SUPPORTED_ALLOWLIST_SCHEMA}); update the tessie-ops plugin or fix the file",
            "allowlist_schema",
        )
    entries = raw.get("vehicles")
    if not isinstance(entries, list):
        raise _denied("allowlist 'vehicles' must be a list", "allowlist_invalid")
    vehicles = tuple(_parse_vehicle(item, i) for i, item in enumerate(entries))
    seen_vins: set[str] = set()
    seen_aliases: set[str] = set()
    for vehicle in vehicles:
        alias_key = norm_alias(vehicle.alias)
        if vehicle.vin in seen_vins or alias_key in seen_aliases:
            raise _denied(
                f"allowlist lists {vehicle.alias!r} twice (VIN or alias duplicate)",
                "allowlist_invalid",
            )
        seen_vins.add(vehicle.vin)
        seen_aliases.add(alias_key)
    default = raw.get("default_vehicle")
    if default is not None:
        if not isinstance(default, str) or norm_alias(default) not in seen_aliases:
            raise _denied("allowlist default_vehicle must name a listed alias", "allowlist_invalid")
    low_battery: int | None = None
    watch = raw.get("watch")
    if watch is not None:
        if not isinstance(watch, dict):
            raise _denied("allowlist 'watch' must be an object", "allowlist_invalid")
        value = watch.get("low_battery_percent")
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 100:
                raise _denied(
                    "watch.low_battery_percent must be an integer 1..100", "allowlist_invalid"
                )
            low_battery = value
    return Allowlist(
        vehicles=vehicles,
        default_vehicle=" ".join(default.split()) if isinstance(default, str) else None,
        owner_chats=_chat_set(raw, "owner_chats"),
        control_chats=_chat_set(raw, "control_chats"),
        read_chats=_chat_set(raw, "read_chats"),
        low_battery_percent=low_battery,
    )


def load_allowlist(path: Path = ALLOWLIST_PATH) -> Allowlist:
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise _denied(
            f"default deny: no allowlist at {path} — create it as described in docs/setup.md "
            "(no vehicle is addressable without one)",
            "allowlist_missing",
        ) from exc
    except OSError as exc:
        raise _denied(f"cannot stat allowlist {path}: {exc}", "allowlist_unreadable") from exc
    if not stat.S_ISREG(info.st_mode):
        raise _denied(
            f"allowlist {path} must be a regular file, not a link or special file",
            "allowlist_invalid",
        )
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise _denied(f"cannot read allowlist {path}: {exc}", "allowlist_unreadable") from exc
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise _denied(
            f"allowlist {path} is not valid JSON ({exc}); fix it, nothing is usable until then",
            "allowlist_invalid",
        ) from exc
    return parse_allowlist(raw)


# --- Chat authorization -------------------------------------------------------


def witnessed_chat_jid(
    *,
    environ_path: Path = WITNESS_ENVIRON_PATH,
    env: Mapping[str, str] | None = None,
) -> str:
    """The chat id the host gave this container, read from the init process environment."""
    process_env = os.environ if env is None else env
    try:
        raw = environ_path.read_bytes()
    except OSError as exc:
        raise _denied(
            f"cannot witness the chat identity from {environ_path}: {exc}. Controls and "
            "location stay denied until the host-provided chat id can be read",
            "chat_unwitnessed",
        ) from exc
    witnessed: str | None = None
    for item in raw.split(b"\0"):
        key, sep, value = item.partition(b"=")
        if sep and key == CHAT_JID_ENV.encode("ascii"):
            witnessed = value.decode("utf-8", errors="replace")
    if not witnessed:
        raise _denied(
            f"the container init environment carries no {CHAT_JID_ENV}; this chat cannot be "
            "authorized",
            "chat_unwitnessed",
        )
    claimed = process_env.get(CHAT_JID_ENV)
    if claimed is not None and claimed != witnessed:
        raise _denied(
            f"{CHAT_JID_ENV} in the command environment disagrees with the host-provided "
            "value; refusing (the host value cannot be overridden from a command line)",
            "chat_identity_mismatch",
        )
    return witnessed


def role_for(chat_jid: str, allowlist: Allowlist) -> str | None:
    if chat_jid in allowlist.owner_chats:
        return ROLE_OWNER
    if chat_jid in allowlist.control_chats:
        return ROLE_CONTROL
    if chat_jid in allowlist.read_chats:
        return ROLE_READ
    return None


def require_role(role: str | None, minimum: str, purpose: str) -> str:
    if role is None:
        raise _denied(
            f"this chat is not authorized for Tessie ({purpose}): add its id to the allowlist "
            "owner_chats, control_chats or read_chats (docs/setup.md)",
            "chat_unauthorized",
        )
    if _ROLE_RANK[role] < _ROLE_RANK[minimum]:
        raise _denied(
            f"this chat's role {role!r} does not permit {purpose}; it needs {minimum!r}",
            "chat_role_insufficient",
        )
    return role


def authorize(
    allowlist: Allowlist,
    minimum: str,
    purpose: str,
    *,
    environ_path: Path = WITNESS_ENVIRON_PATH,
    env: Mapping[str, str] | None = None,
) -> str:
    """Witness the chat, look up its role, require `minimum`. Returns the role."""
    chat = witnessed_chat_jid(environ_path=environ_path, env=env)
    return require_role(role_for(chat, allowlist), minimum, purpose)


# --- Live inventory and selection ---------------------------------------------


def parse_inventory(payload: object) -> dict[str, LiveVehicle]:
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        raise TessieError(
            "Tessie /vehicles answered without a 'results' list; report this response shape",
            code="malformed_response",
        )
    inventory: dict[str, LiveVehicle] = {}
    for item in results:
        if not isinstance(item, dict) or not isinstance(item.get("vin"), str):
            continue
        last_state = item.get("last_state")
        state = last_state if isinstance(last_state, dict) else {}
        config = state.get("vehicle_config")
        car_type = config.get("car_type") if isinstance(config, dict) else None
        access = item.get("access_type")
        active = item.get("is_active")
        display = state.get("display_name")
        vin = item["vin"].upper()
        inventory[vin] = LiveVehicle(
            vin=vin,
            access_type=access if isinstance(access, str) else None,
            is_active=active if isinstance(active, bool) else None,
            display_name=display if isinstance(display, str) else None,
            car_type=car_type if isinstance(car_type, str) else None,
        )
    return inventory


def denied_reason(entry: AllowedVehicle, live: LiveVehicle | None) -> str | None:
    """None when the listed vehicle is addressable, else the stable denied reason."""
    if live is None:
        return DENIED_NOT_IN_INVENTORY
    if entry.shared:
        return None
    if live.access_type != "OWNER":
        return DENIED_NOT_OWNER_ACCESS
    if live.is_active is not True:
        return DENIED_INACTIVE
    return None


def eligible_entries(
    allowlist: Allowlist, inventory: Mapping[str, LiveVehicle]
) -> list[AllowedVehicle]:
    return [v for v in allowlist.vehicles if denied_reason(v, inventory.get(v.vin)) is None]


def _find_entry(selector: str, allowlist: Allowlist) -> AllowedVehicle:
    wanted = selector.strip()
    upper = wanted.upper()
    for vehicle in allowlist.vehicles:
        if vehicle.vin == upper or norm_alias(vehicle.alias) == norm_alias(wanted):
            return vehicle
    reason = DENIED_NOT_ALLOWLISTED if VIN_PATTERN.match(upper) else DENIED_UNKNOWN_ALIAS
    known = ", ".join(sorted(v.alias for v in allowlist.vehicles)) or "none listed"
    raise _denied(
        f"vehicle {wanted!r} is not addressable ({reason}); allowlisted aliases: {known}",
        reason,
    )


def select_vehicle(
    selector: str | None,
    allowlist: Allowlist,
    inventory: Mapping[str, LiveVehicle],
) -> ResolvedVehicle:
    """Resolve an alias/VIN/default to one addressable vehicle, or raise a denial."""
    if selector is None:
        if allowlist.default_vehicle is not None:
            selector = allowlist.default_vehicle
        else:
            candidates = eligible_entries(allowlist, inventory)
            if len(candidates) == 1:
                selector = candidates[0].alias
            else:
                names = ", ".join(sorted(v.alias for v in candidates)) or "none addressable"
                raise _denied(
                    f"choose a vehicle with --vehicle (addressable: {names})", SELECTOR_REQUIRED
                )
    entry = _find_entry(selector, allowlist)
    live = inventory.get(entry.vin)
    reason = denied_reason(entry, live)
    if reason is not None or live is None:
        raise _denied(
            f"vehicle {entry.alias!r} is allowlisted but not addressable now ({reason}); "
            "no request was sent to it",
            reason or DENIED_NOT_IN_INVENTORY,
        )
    return ResolvedVehicle(
        vin=entry.vin, alias=entry.alias, vin_suffix=vin_suffix(entry.vin), live=live
    )


def denied_summary(allowlist: Allowlist, inventory: Mapping[str, LiveVehicle]) -> list[dict]:
    """Owner-chat discovery view of everything NOT addressable. No coordinates, no VINs."""
    listed = {v.vin: v for v in allowlist.vehicles}
    rows: list[dict] = []
    for vin, live in inventory.items():
        entry = listed.get(vin)
        reason = DENIED_NOT_ALLOWLISTED if entry is None else denied_reason(entry, live)
        if reason is None:
            continue
        label = entry.alias if entry is not None else (live.display_name or f"…{vin_suffix(vin)}")
        rows.append(
            {
                "alias_or_suffix": label,
                "access_type": live.access_type,
                "is_active": live.is_active,
                "denied_reason": reason,
            }
        )
    for entry in allowlist.vehicles:
        if entry.vin not in inventory:
            rows.append(
                {
                    "alias_or_suffix": entry.alias,
                    "access_type": None,
                    "is_active": None,
                    "denied_reason": DENIED_NOT_IN_INVENTORY,
                }
            )
    return rows
