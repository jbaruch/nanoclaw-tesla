"""Fixed genuine-main vehicle brief request and exact response validator.

No caller role, route, date, vehicle, policy or effect fields. Co-shipped charge
transport loads the same native broker client; no direct HTTP or fallback.
All numbers and rendered lines are read-only evidence, never control authority.
"""

from __future__ import annotations

import importlib.util
import math
import stat
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

INSTALLED = Path("/home/node/.claude/skills/tessl__tessie-charge/scripts")
DEV = Path(__file__).resolve().parents[2] / "tessie-charge" / "scripts"
CHECKS = ("overnight_unplugged", "insufficient_charge", "tire_warning", "open_vehicle_alert")
TIRES = {
    "front_left": "переднее левое",
    "front_right": "переднее правое",
    "rear_left": "заднее левое",
    "rear_right": "заднее правое",
}


def native_type() -> Any:
    owner = Path(__file__).absolute().parents[1]
    source = owner.name == "tessie-brief" and owner.parent.name == "skills"
    directory = (
        DEV
        if source and not (INSTALLED.parent.exists() or INSTALLED.parent.is_symlink())
        else INSTALLED
    )
    directory = directory.resolve(strict=True)
    target = directory / "charge_ipc.py"
    meta = target.lstat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
        raise ValueError("Reinstall the complete same-provider native transport.")
    spec = importlib.util.spec_from_file_location("tessie_brief_charge_transport", target)
    if spec is None or spec.loader is None:
        raise ValueError("Reinstall the complete same-provider native transport.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.native_type()


def exact(value: object, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("Update the installed vehicle brief reader for this response.")
    return value


def number(value: object, minimum: float, maximum: float) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not minimum <= value <= maximum
    ):
        raise ValueError("Inspect the native vehicle measurement before the brief.")
    return value


def integer(value: object, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Inspect the native vehicle count before the brief.")
    return value


def instant(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("Use a native canonical UTC observation time.")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.isoformat(timespec="milliseconds").replace("+00:00", "Z") != value:
        raise ValueError("Use a native canonical UTC observation time.")
    return result


def alert_text(kind: str, value: object) -> str:
    if kind == "overnight_unplugged":
        d = exact(value, {"battery_percent", "daily_limit_percent", "samples", "start", "end"})
        battery = number(d["battery_percent"], 0, 100)
        limit = integer(d["daily_limit_percent"], 50, 100)
        integer(d["samples"], 2, 1200)
        if instant(d["end"]) <= instant(d["start"]):
            raise ValueError("Inspect complete overnight observation bounds.")
        return (
            "по сохранённым ночным наблюдениям не подключена дома, "
            f"{battery:g}% при дневном лимите {limit}%"
        )
    if kind == "insufficient_charge":
        d = exact(
            value,
            {"shortfall_kwh", "expected_departure_percent", "required_percent", "drive_count"},
        )
        shortfall = number(d["shortfall_kwh"], 0.000000001, 10000000)
        number(d["expected_departure_percent"], 0, 100)
        integer(d["required_percent"], 0, 100)
        integer(d["drive_count"], 1, 2000)
        rounded = math.ceil(shortfall * 10) / 10
        return f"по оценке на сегодняшние поездки не хватает {rounded:g} кВт·ч"
    if kind == "tire_warning":
        d = exact(value, {"positions"})
        positions = d["positions"]
        if (
            not isinstance(positions, list)
            or not positions
            or len(positions) > 4
            or any(not isinstance(p, str) or p not in TIRES for p in positions)
            or len(set(positions)) != len(positions)
        ):
            raise ValueError("Inspect the native tire warning positions.")
        return "низкое давление: " + ", ".join(TIRES[p] for p in positions)
    if kind == "open_vehicle_alert":
        d = exact(value, {"flags"})
        if d["flags"] != ["not_enough_power_to_heat"]:
            raise ValueError(
                "Update the current vehicle-warning reader; do not relabel alert history."
            )
        return "недостаточно мощности для прогрева батареи"
    raise ValueError("Update the installed vehicle brief reader for this condition.")


def project(value: object) -> dict[str, Any]:
    result = exact(
        value,
        {
            "schema_version",
            "day",
            "home_timezone",
            "observed_at",
            "checked_vehicles",
            "coverage",
            "uncovered_sources",
            "vehicles",
        },
    )
    integer(result["schema_version"], 1, 1)
    observed = instant(result["observed_at"])
    zone = result["home_timezone"]
    missing_home = zone is None and result["day"] is None
    if not missing_home:
        if not isinstance(zone, str) or not zone or len(zone) > 100 or zone != zone.strip():
            raise ValueError("Inspect the native home timezone binding.")
        if observed.astimezone(ZoneInfo(zone)).date().isoformat() != result["day"]:
            raise ValueError("Inspect the native home-day binding.")
    count = integer(result["checked_vehicles"], 0, 100)
    if result["coverage"] != "partial" or result["uncovered_sources"] != ["firmware_active_status"]:
        raise ValueError("Do not claim complete firmware-active coverage from history.")
    vehicles = result["vehicles"]
    if not isinstance(vehicles, list) or len(vehicles) != count:
        raise ValueError("Inspect the complete current fleet readback.")
    aliases: set[str] = set()
    lines = []
    for row in vehicles:
        vehicle = exact(row, {"alias", "alerts", "unknown_checks"})
        alias = vehicle["alias"]
        if (
            not isinstance(alias, str)
            or not alias.strip()
            or len(alias) > 100
            or any(unicodedata.category(c) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for c in alias)
            or len(alias.encode("utf-16-le")) > 200
            or alias in aliases
        ):
            raise ValueError("Inspect the current native vehicle aliases.")
        aliases.add(alias)
        unknown = vehicle["unknown_checks"]
        if (
            not isinstance(unknown, list)
            or any(not isinstance(v, str) or v not in CHECKS for v in unknown)
            or len(set(unknown)) != len(unknown)
        ):
            raise ValueError("Inspect explicit vehicle source coverage.")
        if missing_home and not {"overnight_unplugged", "insufficient_charge"}.issubset(unknown):
            raise ValueError("Keep missing native home-clock planning checks unknown.")
        alerts = vehicle["alerts"]
        if not isinstance(alerts, list) or len(alerts) > 4:
            raise ValueError("Inspect the finite vehicle brief conditions.")
        kinds: set[str] = set()
        texts = []
        for raw in alerts:
            alert = exact(raw, {"kind", "detail"})
            kind = alert["kind"]
            if not isinstance(kind, str) or kind not in CHECKS or kind in kinds or kind in unknown:
                raise ValueError("Inspect duplicate or conflicting vehicle evidence.")
            kinds.add(kind)
            texts.append(alert_text(kind, alert["detail"]))
        if texts:
            lines.append(alias + ": " + "; ".join(texts) + ".")
    return {**result, "lines": lines}


def call() -> dict[str, Any]:
    bridge = native_type()()
    bridge.message_type = "tessie_brief_request"
    reply = bridge.call({"schema_version": 1, "operation": "summary"}, 200)
    if reply.get("status") != 200:
        raise ValueError("Inspect the installed vehicle brief authority.")
    return project(reply.get("data"))
