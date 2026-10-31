"""Fixed genuine-main vehicle brief request and exact response validator.

No caller role, route, date, vehicle, policy or effect fields. Co-shipped charge
transport loads the same native broker client; no direct HTTP or fallback.
All numbers and rendered lines are read-only evidence, never control authority.
"""

from __future__ import annotations

import builtins
import hashlib
import importlib.abc
import importlib.machinery
import importlib.util
import json
import math
import os
import re
import stat
import sys
import unicodedata
from contextlib import ExitStack
from datetime import datetime
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NoReturn
from zoneinfo import ZoneInfo

INSTALLED = Path("/home/node/.claude/skills/tessl__tessie-charge/scripts")
PROVIDER = Path("/home/node/.claude/.tessl/tiles/jbaruch/nanoclaw-tesla")
CHECKS = ("overnight_unplugged", "insufficient_charge", "tire_warning", "open_vehicle_alert")
TIRES = {
    "front_left": "переднее левое",
    "front_right": "переднее правое",
    "rear_left": "заднее левое",
    "rear_right": "заднее правое",
}


RULE_DECLARATIONS = (
    (
        "- The provider is ",
        "- The provider is `jbaruch/nanoclaw-tesla`.",
    ),
    (
        "- The authored scope is ",
        "- The authored scope is `skills/tessie-brief/` and the optional "
        "`jbaruch/nanoclaw-admin` morning-brief source that consumes it.",
    ),
    (
        "- Co-shipped executable target: ",
        "- Co-shipped executable target: `skills/tessie-brief/scripts/tessie-brief.py`.",
    ),
    (
        "- Co-shipped pure validator target: ",
        "- Co-shipped pure validator target: "
        "`skills/tessie-brief/scripts/brief_ipc.py`, function `project(value)`.",
    ),
    (
        "- The executable takes ",
        "- The executable takes no arguments and returns exactly "
        "`{wake_agent:false,data}` on exit 0; exit 1 has fixed stderr and no stdout.",
    ),
    (
        "- `project(value)` accepts ",
        "- `project(value)` accepts the Host schema1 data object without `lines`, "
        "validates its complete fields and returns that object plus canonical literal"
        " lines; invalid supported input raises `ValueError` or an unknown-zone "
        "error, with no provider I/O.",
    ),
    (
        "- The fixed native transport closure is ",
        "- The fixed native transport closure is the same provider's "
        "`skills/tessie-charge/scripts/charge_ipc.py` and "
        "`skills/tessie-ops/scripts/tessie_native.py` plus "
        "`skills/tessie-ops/scripts/tessie_core.py`.",
    ),
    (
        "- Read the complete ",
        "- Read the complete `skills/tessie-brief/references/host-contract.md` in "
        "this installed provider before producing or using summary output.",
    ),
)


def _declares_rule(raw):
    lines = [line.strip() for line in raw.decode("utf-8").splitlines()]
    return all(
        [line for line in lines if line.startswith(prefix)] == [expected]
        for prefix, expected in RULE_DECLARATIONS
    )


def _repair() -> NoReturn:
    raise ValueError(
        "Reinstall the complete same-provider read-only vehicle brief; preserve other sources."
    )


def _identity(meta):
    return (meta.st_dev, meta.st_ino, meta.st_mode, meta.st_uid, meta.st_gid)


def _file_snapshot(file: Path):
    """Fixed public source read through held, no-follow component descriptors."""
    if not file.is_absolute() or ".." in file.parts:
        _repair()
    with ExitStack() as opened:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        fd = os.open("/", flags)
        opened.callback(os.close, fd)
        parents: list[tuple[int, int | None, str, os.stat_result]] = [(fd, None, "/", os.fstat(fd))]
        for name in file.parts[1:-1]:
            parent = fd
            fd = os.open(name, flags, dir_fd=parent)
            opened.callback(os.close, fd)
            parents.append((fd, parent, name, os.fstat(fd)))
        parent = fd
        fd = os.open(file.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        opened.callback(os.close, fd)
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or not 0 < before.st_size <= 128 * 1024
        ):
            _repair()
        raw = os.read(fd, before.st_size + 1)

        def stamp(meta):
            return (
                _identity(meta),
                meta.st_nlink,
                meta.st_size,
                meta.st_mtime_ns,
                meta.st_ctime_ns,
            )

        if (
            len(raw) != before.st_size
            or stamp(before) != stamp(os.fstat(fd))
            or stamp(before) != stamp(os.stat(file.name, dir_fd=parent, follow_symlinks=False))
        ):
            _repair()
        for held, parent, name, meta in parents:
            named = (
                os.stat(name, dir_fd=parent, follow_symlinks=False)
                if parent is not None
                else os.lstat("/")
            )
            if _identity(meta) != _identity(os.fstat(held)) or _identity(meta) != _identity(named):
                _repair()
        return raw, (
            stamp(before),
            tuple(_identity(meta) for _, _, _, meta in parents),
            hashlib.sha256(raw).hexdigest(),
        )


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            _repair()
        value[key] = item
    return value


class _BriefProvider:
    """One fixed provider snapshot, never a caller-selected transport or grant."""

    targets = (
        "skills/tessie-brief/scripts/tessie-brief.py",
        "skills/tessie-brief/scripts/brief_ipc.py",
        "skills/tessie-charge/scripts/charge_ipc.py",
        "skills/tessie-ops/scripts/tessie_native.py",
        "skills/tessie-ops/scripts/tessie_core.py",
    )

    def __init__(self):
        own = Path(__file__).absolute()
        skill = own.parents[1]
        self.source = (
            skill.name == "tessie-brief"
            and skill.parent.name == "skills"
            and not (INSTALLED.parent.exists() or INSTALLED.parent.is_symlink())
        )
        if not self.source and skill.name != "tessl__tessie-brief":
            _repair()
        self.root = own.parents[3] if self.source else PROVIDER
        self.native = skill.parent
        self.own = own
        self.binding, self.sources = self.capture()

    def target(self, relative):
        if self.source:
            return self.root / relative
        _, skill, *parts = Path(relative).parts
        return self.native / ("tessl__" + skill) / Path(*parts)

    def capture(self):
        rule = "rules/vehicle-brief-policy.md"
        reference = "skills/tessie-brief/references/host-contract.md"
        paths = (".tessl-plugin/plugin.json", rule, reference, *self.targets)
        values, binding = {}, {}
        try:
            for relative in paths:
                values[relative], binding[relative] = _file_snapshot(self.root / relative)
            manifest = json.loads(values[paths[0]], object_pairs_hook=_unique)
            if (
                not isinstance(manifest, dict)
                or manifest.get("name") != "jbaruch/nanoclaw-tesla"
                or not isinstance(manifest.get("version"), str)
                or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", manifest["version"])
            ):
                _repair()
            for field, required in [
                ("skills", {"skills/tessie-brief", "skills/tessie-charge", "skills/tessie-ops"}),
                ("rules", {rule, "rules/nanoclaw-skill-root.md"}),
            ]:
                entries = manifest.get(field)
                if (
                    not isinstance(entries, list)
                    or not all(isinstance(item, str) for item in entries)
                    or not required.issubset(entries)
                ):
                    _repair()
            if not _declares_rule(values[rule]) or re.findall(
                r"^Contract: ([A-Za-z0-9-]+)$", values[reference].decode("utf-8"), re.MULTILINE
            ) != ["tessie-morning-brief-consumer-v1"]:
                _repair()
            for relative in self.targets:
                raw, token = _file_snapshot(self.target(relative))
                if raw != values[relative]:
                    _repair()
                binding["native:" + relative] = token
            if self.target(self.targets[1]) != self.own:
                _repair()
            return binding, {relative: values[relative] for relative in self.targets}
        except OSError as error:
            raise ValueError(
                "Restore the contained regular read-only Tesla provider and matching native copies."
            ) from error

    def verify(self):
        current, _ = self.capture()
        if current != self.binding:
            _repair()


def native_type() -> Any:
    binding = _BriefProvider()
    core_path = "skills/tessie-ops/scripts/tessie_core.py"
    native_path = "skills/tessie-ops/scripts/tessie_native.py"
    charge_path = "skills/tessie-charge/scripts/charge_ipc.py"

    def source_module(name, relative, importer):
        # Fixed, captured provider source only: never SourceFileLoader or PYC.
        if (name, relative) not in {
            ("_tessie_brief_verified_core", core_path),
            ("tessie_brief_charge_transport", charge_path),
        } or name in sys.modules:
            _repair()
        spec = importlib.machinery.ModuleSpec(name, loader=None)
        module = importlib.util.module_from_spec(spec)
        module.__file__ = str(binding.target(relative))
        vars(module)["__builtins__"] = {**vars(builtins), "__import__": importer}
        binding.verify()
        exec(
            compile(binding.sources[relative], module.__file__, "exec", dont_inherit=True),
            vars(module),
        )
        binding.verify()
        return module

    def standard_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level or name.startswith("tessie_"):
            _repair()
        return builtins.__import__(name, globals, locals, fromlist, level)

    core = source_module("_tessie_brief_verified_core", core_path, standard_import)

    def native_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "tessie_core" and level == 0:
            return core
        return standard_import(name, globals, locals, fromlist, level)

    class NativeLoader(importlib.abc.Loader):
        def create_module(self, spec):
            return None

        def exec_module(self, module):
            module.__file__ = str(binding.target(native_path))
            vars(module)["__builtins__"] = {**vars(builtins), "__import__": native_import}
            binding.verify()
            exec(
                compile(binding.sources[native_path], module.__file__, "exec", dont_inherit=True),
                vars(module),
            )
            binding.verify()

    native_spec = importlib.machinery.ModuleSpec("tessie_charge_native", NativeLoader())

    def native_spec_for(name, path):
        if name != native_spec.name or Path(path) != binding.target(native_path):
            _repair()
        binding.verify()
        return native_spec

    def native_from_spec(spec):
        if spec is not native_spec:
            _repair()
        return importlib.util.module_from_spec(spec)

    # These views belong only to the private charge module. No global module,
    # importlib function or sys.path entry is replaced or trusted as provider code.
    local_importlib = SimpleNamespace(
        util=SimpleNamespace(
            spec_from_file_location=native_spec_for,
            module_from_spec=native_from_spec,
        )
    )
    local_sys = SimpleNamespace(path=[], modules={"tessie_core": core})

    def charge_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name == "importlib.util":
            return local_importlib
        if level == 0 and name == "sys":
            return local_sys
        return standard_import(name, globals, locals, fromlist, level)

    module = source_module("tessie_brief_charge_transport", charge_path, charge_import)
    native = module.native_type()
    binding.verify()

    class BoundNative(native):
        def __init__(self, *args, **kwargs):
            binding.verify()
            super().__init__(*args, **kwargs)
            binding.verify()

        def call(self, payload, timeout):
            binding.verify()
            try:
                return super().call(payload, timeout)
            finally:
                binding.verify()

    return BoundNative


def exact(value: object, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("Update the installed vehicle brief reader for this response.")
    return value


def number(value: object, minimum: float, maximum: float) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not minimum <= value <= maximum
        or not math.isfinite(value)
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
        # Round the validated JSON number upward without losing precision in a
        # binary multiply. Do not guess or erase computed-input noise.
        rounded = Decimal(repr(shortfall)).quantize(Decimal("0.1"), rounding=ROUND_CEILING)
        amount = format(rounded, "f").removesuffix(".0")
        return f"по оценке на сегодняшние поездки не хватает {amount} кВт·ч"
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
