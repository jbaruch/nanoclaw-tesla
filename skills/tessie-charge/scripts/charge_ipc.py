"""Fixed calendar-charge native IPC; no HTTP, policy writer or direct control.

call accepts poll/status without fields, or estimate with an exact native
alias/VIN carried as one literal vehicle value by the bounded argv adapter,
distance_km and departure fields. Native registered-main identity, installed
contracts and protected owner enrollment are enforced by the host. A caller
cannot supply those facts. One request is published; uncertain polls never retry.
"""

from __future__ import annotations

import importlib.util
import math
import re
import stat
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

OPS = Path("/home/node/.claude/skills/tessl__tessie-ops/scripts")
DEV_OPS = Path(__file__).resolve().parents[2] / "tessie-ops" / "scripts"


def native_type() -> Any:
    directory = OPS if OPS.parent.exists() or OPS.parent.is_symlink() else DEV_OPS
    directory = directory.resolve(strict=True)
    for name in ("tessie_core.py", "tessie_native.py"):
        target = directory / name
        meta = target.lstat()
        if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
            raise ValueError("Reinstall the complete native Tessie provider.")
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    existing = sys.modules.get("tessie_core")
    if existing is not None and (
        existing.__file__ is None
        or Path(existing.__file__).resolve() != directory / "tessie_core.py"
    ):
        raise ValueError("Use the same installed native Tessie provider.")
    spec = importlib.util.spec_from_file_location(
        "tessie_charge_native", directory / "tessie_native.py"
    )
    if spec is None or spec.loader is None:
        raise ValueError("Reinstall the complete native Tessie transport.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.NativeIPC


def number(value: object, minimum: float, maximum: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and minimum <= value <= maximum
        and math.isfinite(value)
    )


def validate_input(operation: str, fields: dict[str, object]) -> None:
    if operation not in {"poll", "status", "estimate"}:
        raise ValueError("Use one documented calendar-charge operation.")
    if set(fields) != (
        {"vehicle", "distance_km", "departure"} if operation == "estimate" else set()
    ):
        raise ValueError("Supply only the selected operation's planning fields.")
    if operation != "estimate":
        return
    vehicle, departure = fields["vehicle"], fields["departure"]
    if (
        not isinstance(vehicle, str)
        or not vehicle
        or len(vehicle) > 100
        or any(ord(char) < 32 or ord(char) == 127 for char in vehicle)
        or not number(fields["distance_km"], 0, 100000)
        or not isinstance(departure, str)
        or re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})",
            departure,
        )
        is None
    ):
        raise ValueError("Use a literal vehicle, finite distance and zoned departure.")
    datetime.fromisoformat(departure)


def call(operation: str, fields: dict[str, object] | None = None) -> dict[str, Any]:
    values = {} if fields is None else fields
    validate_input(operation, values)
    bridge = native_type()()
    bridge.message_type = "tessie_charge_request"
    reply = bridge.call({"schema_version": 1, "operation": operation, **values}, 200)
    result = reply.get("data")
    if (
        reply.get("status") != 200
        or not isinstance(result, dict)
        or type(result.get("schema_version")) is not int
        or result["schema_version"] != 1
    ):
        raise ValueError(
            "Inspect installed charging authority and retain uncertain control history."
        )
    return result
