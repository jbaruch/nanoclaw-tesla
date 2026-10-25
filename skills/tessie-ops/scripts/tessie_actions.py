"""Read, command and confirmation flows behind the tessie-*.py CLIs.

Read path: status probe first, then the cached read. It never calls
`POST /{vin}/wake` and never sets `use_cache=false`; a sleeping car is
answered from Tessie's cache and says so.

Command path: validate parameters, resolve the vehicle through the allowlist,
require the caller to echo `<alias>:<action>`, send one Tessie command
(`wait_for_completion=true`, `max_attempts` at most `MAX_COMMAND_ATTEMPTS`),
then read the cached state back. Tessie's `{"result": true}` only means the
command was accepted, so the outcome is one of:

- `confirmed`   — accepted, and a fresh state read shows the expected field value
- `accepted`    — accepted, and the action has no state field to compare (flash, share, tag)
- `unconfirmed` — accepted, but the readback is stale, mismatched or missing
- `failed`      — Tessie answered `{"result": false}`
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from tessie_core import (
    COMMAND_OPS,
    MAX_COMMAND_ATTEMPTS,
    Clock,
    TessieClient,
    TessieError,
    redact_location,
)
from tessie_policy import (
    Allowlist,
    LiveVehicle,
    ResolvedVehicle,
    parse_inventory,
    select_vehicle,
)

# A state section older than the command by more than this is stale evidence.
FRESHNESS_SLACK_SECONDS = 15
TEMPERATURE_TOLERANCE_C = 0.5
CHARGE_LIMIT_RANGE = (50, 100)
TEMPERATURE_RANGE_C = (15.0, 28.0)
SHARE_MAX_LENGTH = 500
TAG_MAX_LENGTH = 64

LOCALE_PATTERN = re.compile(r"^[a-z]{2}-[A-Z]{2}$")
DRIVES_PATTERN = re.compile(r"^[0-9]+(,[0-9]+)*$")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

# Reads that never contain precise location and need only a read role.
PLAIN_READS = (
    "status",
    "state",
    "battery",
    "tire_pressure",
    "firmware_alerts",
    "consumption_since_charge",
    "last_idle_state",
    "drives",
)
# Reads that are owner-only: the live position itself, and who else can drive.
OWNER_READS = ("location", "drivers")
READ_KINDS = (*PLAIN_READS, *OWNER_READS)
# Reads whose payload embeds coordinates or addresses and so need redaction.
LOCATION_BEARING_READS = ("state", "drives", "location", "battery", "tire_pressure")


@dataclass(frozen=True)
class CommandSpec:
    """How to validate one control and how to read its effect back."""

    needs: tuple[str, ...]  # required parameter names
    section: str | None  # state section holding the effect, None when there is none
    field: str | None
    expected: Callable[[Mapping[str, Any]], Any] | None


def _expect_charging(_: Mapping[str, Any]) -> Any:
    return ("Charging", "Starting")


COMMAND_SPECS: dict[str, CommandSpec] = {
    "lock": CommandSpec((), "vehicle_state", "locked", lambda _: True),
    "unlock": CommandSpec((), "vehicle_state", "locked", lambda _: False),
    "start_climate": CommandSpec((), "climate_state", "is_climate_on", lambda _: True),
    "stop_climate": CommandSpec((), "climate_state", "is_climate_on", lambda _: False),
    "set_temperatures": CommandSpec(
        ("temperature",), "climate_state", "driver_temp_setting", lambda p: p["temperature"]
    ),
    "start_charging": CommandSpec((), "charge_state", "charging_state", _expect_charging),
    "stop_charging": CommandSpec((), "charge_state", "charging_state", lambda _: ("Stopped",)),
    "set_charge_limit": CommandSpec(
        ("percent",), "charge_state", "charge_limit_soc", lambda p: p["percent"]
    ),
    "share": CommandSpec(("value",), None, None, None),
    "flash": CommandSpec((), None, None, None),
}
if set(COMMAND_SPECS) != set(COMMAND_OPS):  # keep the two tables in lock-step
    raise RuntimeError("COMMAND_SPECS and COMMAND_OPS drifted apart")


def iso_utc(epoch_seconds: float) -> str:
    return datetime.fromtimestamp(epoch_seconds, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Inventory ----------------------------------------------------------------


def fetch_inventory(client: TessieClient) -> dict[str, LiveVehicle]:
    return parse_inventory(client.get("vehicles"))


def resolve(client: TessieClient, allowlist: Allowlist, selector: str | None) -> ResolvedVehicle:
    """One cached `GET /vehicles`, then allowlist + live-access resolution."""
    return select_vehicle(selector, allowlist, fetch_inventory(client))


# --- Reads --------------------------------------------------------------------


def read_vehicle(
    client: TessieClient,
    vehicle: ResolvedVehicle,
    kind: str,
    *,
    include_location: bool,
    query: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Status-gated cached read. `include_location` must already be role-checked."""
    if kind not in READ_KINDS:
        raise TessieError(f"unsupported read {kind!r}", code="unsupported_read")
    status_payload = client.get("status", vin=vehicle.vin)
    vehicle_status = status_payload.get("status") if isinstance(status_payload, dict) else None
    if not isinstance(vehicle_status, str):
        raise TessieError(
            "Tessie /status answered without a status string; report this response shape",
            code="malformed_response",
        )
    result: dict[str, Any] = {
        "vehicle": {"alias": vehicle.alias, "vin_suffix": vehicle.vin_suffix},
        "kind": kind,
        "vehicle_status": vehicle_status,
        "from_cache": vehicle_status != "awake",
    }
    if kind == "status":
        return result
    # Cached read: use_cache stays at Tessie's default and no wake is ever sent.
    data = client.get(kind, vin=vehicle.vin, query=query)
    if kind in LOCATION_BEARING_READS and not include_location:
        data, dropped = redact_location(data)
        result["location_redacted"] = dropped
    result["data"] = data
    return result


# --- Command parameter validation ---------------------------------------------


def _clean_text(value: str, label: str, limit: int) -> str:
    text = value.strip()
    if not text or len(text) > limit or _CONTROL_CHARS.search(text):
        raise TessieError(f"{label} must be 1..{limit} printable characters", code="bad_parameter")
    return text


def build_params(op: str, raw: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalise the parameters one control needs; reject extras."""
    spec = COMMAND_SPECS[op]
    allowed = set(spec.needs) | ({"locale"} if op == "share" else set())
    supplied = {k: v for k, v in raw.items() if v is not None}
    extra = sorted(set(supplied) - allowed)
    if extra:
        raise TessieError(
            f"{op} does not take {', '.join('--' + e for e in extra)}", code="bad_parameter"
        )
    missing = [name for name in spec.needs if name not in supplied]
    if missing:
        raise TessieError(
            f"{op} requires {', '.join('--' + m for m in missing)}", code="bad_parameter"
        )
    params: dict[str, Any] = {}
    if op == "set_temperatures":
        temperature = supplied["temperature"]
        low, high = TEMPERATURE_RANGE_C
        if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
            raise TessieError("temperature must be a number in °C", code="bad_parameter")
        if not low <= float(temperature) <= high:
            raise TessieError(
                f"temperature must be {low:g}..{high:g} °C, got {temperature}", code="bad_parameter"
            )
        params["temperature"] = float(temperature)
    elif op == "set_charge_limit":
        percent = supplied["percent"]
        low_p, high_p = CHARGE_LIMIT_RANGE
        if isinstance(percent, bool) or not isinstance(percent, int):
            raise TessieError("percent must be a whole number", code="bad_parameter")
        if not low_p <= percent <= high_p:
            raise TessieError(
                f"percent must be {low_p}..{high_p}, got {percent}", code="bad_parameter"
            )
        params["percent"] = percent
    elif op == "share":
        params["value"] = _clean_text(str(supplied["value"]), "value", SHARE_MAX_LENGTH)
        locale = str(supplied.get("locale", "en-US"))
        if not LOCALE_PATTERN.match(locale):
            raise TessieError("locale must look like en-US", code="bad_parameter")
        params["locale"] = locale
    return params


def confirmation_phrase(alias: str, op: str) -> str:
    return f"{alias}:{op}"


# --- Confirmation -------------------------------------------------------------


def _section_timestamp(state: Mapping[str, Any], section: str) -> float | None:
    body = state.get(section)
    stamp = body.get("timestamp") if isinstance(body, dict) else None
    if isinstance(stamp, bool) or not isinstance(stamp, (int, float)):
        return None
    return float(stamp) / 1000.0  # Tesla state timestamps are epoch milliseconds


def _matches(observed: Any, expected: Any, field: str) -> bool:
    if isinstance(expected, tuple):
        return observed in expected
    if field == "driver_temp_setting":
        return isinstance(observed, (int, float)) and (
            abs(float(observed) - float(expected)) <= TEMPERATURE_TOLERANCE_C
        )
    return observed == expected


def confirm_state(
    client: TessieClient,
    vehicle: ResolvedVehicle,
    op: str,
    params: Mapping[str, Any],
    *,
    since_epoch: float,
) -> dict[str, Any]:
    """Cached `GET /state` readback compared with what `op` should have changed.

    Returns `{"status": "confirmed"|"unconfirmed"|"accepted", ...}`. A match on a section
    older than `since_epoch - FRESHNESS_SLACK_SECONDS` is stale evidence, not confirmation.
    """
    spec = COMMAND_SPECS[op]
    if spec.section is None or spec.field is None or spec.expected is None:
        return {
            "status": "accepted",
            "reason": "no_state_field",
            "note": f"{op} changes nothing the vehicle state reports; acceptance only",
        }
    state = client.get("state", vin=vehicle.vin)
    if not isinstance(state, dict):
        raise TessieError(
            "Tessie /state answered with a non-object; report this response shape",
            code="malformed_response",
        )
    section = state.get(spec.section)
    observed = section.get(spec.field) if isinstance(section, dict) else None
    expected = spec.expected(params)
    stamp = _section_timestamp(state, spec.section)
    detail: dict[str, Any] = {
        "field": f"{spec.section}.{spec.field}",
        "expected": list(expected) if isinstance(expected, tuple) else expected,
        "observed": observed,
        "state_timestamp": iso_utc(stamp) if stamp is not None else None,
    }
    if observed is None:
        return {"status": "unconfirmed", "reason": "field_missing", **detail}
    if not _matches(observed, expected, spec.field):
        return {"status": "unconfirmed", "reason": "mismatch", **detail}
    if stamp is None:
        return {"status": "unconfirmed", "reason": "no_timestamp", **detail}
    if stamp < since_epoch - FRESHNESS_SLACK_SECONDS:
        return {"status": "unconfirmed", "reason": "stale_state", **detail}
    return {"status": "confirmed", "reason": None, **detail}


# --- Commands -----------------------------------------------------------------


def plan_for(vehicle: ResolvedVehicle, op: str, params: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "vehicle": {"alias": vehicle.alias, "vin_suffix": vehicle.vin_suffix},
        "action": op,
        "params": dict(params),
        "confirm_with": confirmation_phrase(vehicle.alias, op),
    }


def run_command(
    client: TessieClient,
    vehicle: ResolvedVehicle,
    op: str,
    params: Mapping[str, Any],
    *,
    max_attempts: int,
    now: Clock,
) -> dict[str, Any]:
    """Send one control and report acceptance separately from confirmed state."""
    if not 1 <= max_attempts <= MAX_COMMAND_ATTEMPTS:
        raise TessieError(
            f"--max-attempts must be 1..{MAX_COMMAND_ATTEMPTS}", code="bad_max_attempts"
        )
    sent_at = now()
    reply = client.command(op, vin=vehicle.vin, params=params, max_attempts=max_attempts)
    accepted = reply.get("result") if isinstance(reply, dict) else None
    if not isinstance(accepted, bool):
        raise TessieError(
            f"Tessie {op} answered without a boolean result; report this response shape",
            code="malformed_response",
        )
    outcome: dict[str, Any] = {
        "vehicle": {"alias": vehicle.alias, "vin_suffix": vehicle.vin_suffix},
        "action": op,
        "params": dict(params),
        "tessie_result": accepted,
        "max_attempts": max_attempts,
        "sent_at": iso_utc(sent_at),
        "sent_at_epoch": sent_at,
    }
    if not accepted:
        outcome["status"] = "failed"
        outcome["reason"] = "tessie_result_false"
        return outcome
    outcome.update(confirm_state(client, vehicle, op, params, since_epoch=sent_at))
    return outcome


def run_drive_tag(
    client: TessieClient,
    vehicle: ResolvedVehicle,
    *,
    drives: str,
    tag: str | None,
) -> dict[str, Any]:
    """Tag drive records. Not a vehicle actuator: acceptance is all Tessie reports."""
    if not DRIVES_PATTERN.match(drives):
        raise TessieError("--drives must be comma-separated drive ids", code="bad_parameter")
    clean_tag = _clean_text(tag, "tag", TAG_MAX_LENGTH) if tag is not None else None
    reply = client.set_drive_tag(vin=vehicle.vin, drives=drives, tag=clean_tag)
    accepted = reply.get("result") if isinstance(reply, dict) else None
    if not isinstance(accepted, bool):
        raise TessieError(
            "Tessie set_tag answered without a boolean result; report this response shape",
            code="malformed_response",
        )
    return {
        "vehicle": {"alias": vehicle.alias, "vin_suffix": vehicle.vin_suffix},
        "action": "set_drive_tag",
        "params": {"drives": drives, "tag": clean_tag},
        "tessie_result": accepted,
        "status": "accepted" if accepted else "failed",
        "reason": None if accepted else "tessie_result_false",
    }
