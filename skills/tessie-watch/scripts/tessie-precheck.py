#!/usr/bin/env python3
"""Precheck for `tessl__tessie-watch`: wake the agent only when a vehicle needs attention.

Stdout's last line is the scheduler contract:
`{"wake_agent": bool, "data": {...}}`. `wake_agent` is false (and the model never
runs) while every addressable vehicle is healthy. It is true, with the evidence in
`data`, when:

- a `tessie-ops` script fails or times out (revoked token, bad allowlist, Tessie
  down) — setup failures use `data.reason`; per-vehicle failures use
  `data.alerts[].kind` `script_failed`, `script_timeout` or `bad_output` and
  do not discard earlier alerts or prevent checking later vehicles;
- a cached state read lacks the battery fields — `data.alerts[].kind` is
  `state_incomplete`;
- a vehicle's battery is below the threshold and it is not plugged in —
  `data.alerts[].kind` is `low_battery_unplugged`.

The threshold is the allowlist's `watch.low_battery_percent`, else
`DEFAULT_LOW_BATTERY_PERCENT`. All data comes from the co-shipped `tessie-ops`
scripts by subprocess: cached reads only, no wake, no coordinates in `data`.
This foundation check is not a Tesla2-7 feature; those skills compose the same
`tessie-ops` scripts and bring their own prechecks.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

# Installed skill root inside the agent container; the dev-clone sibling is used
# only when that mount is absent (unit tests, local runs).
OPS_SCRIPTS_MOUNT = Path("/home/node/.claude/skills/tessl__tessie-ops/scripts")
OPS_SCRIPTS_DEV = Path(__file__).resolve().parents[2] / "tessie-ops" / "scripts"
REQUIRED_OPS_SCRIPTS = ("tessie-vehicles.py", "tessie-read.py", "tessie-allowlist.py")

DEFAULT_LOW_BATTERY_PERCENT = 20
# A full pass is one inventory call plus a status+state read per vehicle.
SCRIPT_TIMEOUT_SECONDS = 240
STDERR_EXCERPT = 300

Runner = Callable[[Sequence[str]], "subprocess.CompletedProcess[str]"]


class WatchFailure(Exception):
    def __init__(self, reason: str, detail: str, **extra: Any) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail
        self.extra = extra


def ops_scripts_dir() -> Path:
    directory = OPS_SCRIPTS_MOUNT if OPS_SCRIPTS_MOUNT.is_dir() else OPS_SCRIPTS_DEV
    missing = [n for n in REQUIRED_OPS_SCRIPTS if not (directory / n).is_file()]
    if missing:
        raise WatchFailure(
            "script_failed",
            f"tessie-ops scripts missing in {directory}: {', '.join(missing)}; reinstall "
            "the nanoclaw-tesla plugin",
        )
    return directory


def default_runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *argv],
        capture_output=True,
        text=True,
        timeout=SCRIPT_TIMEOUT_SECONDS,
        check=False,
    )


def call_ops(runner: Runner, directory: Path, script: str, *args: str) -> dict[str, Any]:
    try:
        done = runner([str(directory / script), *args])
    except subprocess.TimeoutExpired as exc:
        raise WatchFailure(
            "script_timeout", f"{script} exceeded {SCRIPT_TIMEOUT_SECONDS}s", script=script
        ) from exc
    if done.returncode != 0:
        raise WatchFailure(
            "script_failed",
            done.stderr.strip()[:STDERR_EXCERPT] or f"{script} exited {done.returncode}",
            script=script,
            exit_code=done.returncode,
        )
    try:
        payload = json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        raise WatchFailure(
            "bad_output", f"{script} printed non-JSON stdout", script=script
        ) from exc
    if not isinstance(payload, dict):
        raise WatchFailure("bad_output", f"{script} printed a non-object", script=script)
    return payload


def alerts_for(alias: str, state: dict[str, Any], threshold: int) -> list[dict[str, Any]]:
    data = state.get("data")
    charge = data.get("charge_state") if isinstance(data, dict) else None
    level = charge.get("battery_level") if isinstance(charge, dict) else None
    charging = charge.get("charging_state") if isinstance(charge, dict) else None
    if (
        isinstance(level, bool)
        or not isinstance(level, (int, float))
        or not 0 <= level <= 100
        or not math.isfinite(level)
    ):
        return [
            {"alias": alias, "kind": "state_incomplete", "missing": "charge_state.battery_level"}
        ]
    if not isinstance(charging, str) or charging not in {
        "Disconnected",
        "Charging",
        "Starting",
        "Complete",
        "Stopped",
        "NoPower",
    }:
        return [
            {"alias": alias, "kind": "state_incomplete", "missing": "charge_state.charging_state"}
        ]
    if level < threshold and charging == "Disconnected":
        return [
            {
                "alias": alias,
                "kind": "low_battery_unplugged",
                "battery_level": level,
                "threshold": threshold,
                "vehicle_status": state.get("vehicle_status"),
            }
        ]
    return []


def decide(runner: Runner, directory: Path) -> dict[str, Any]:
    show = call_ops(runner, directory, "tessie-allowlist.py", "show")
    watch = show.get("watch")
    configured = watch.get("low_battery_percent") if isinstance(watch, dict) else None
    threshold = configured if isinstance(configured, int) else DEFAULT_LOW_BATTERY_PERCENT
    listing = call_ops(runner, directory, "tessie-vehicles.py")
    vehicles = listing.get("vehicles")
    if not isinstance(vehicles, list):
        raise WatchFailure("bad_output", "tessie-vehicles.py printed no vehicles list")
    alerts: list[dict[str, Any]] = []
    for index, row in enumerate(vehicles):
        alias = row.get("alias") if isinstance(row, dict) else None
        if not isinstance(alias, str) or not alias.strip():
            alerts.append(
                {
                    "kind": "bad_output",
                    "vehicle_index": index,
                    "error": "tessie-vehicles.py printed a row without a valid alias",
                }
            )
            continue
        try:
            state = call_ops(runner, directory, "tessie-read.py", "state", "--vehicle", alias)
        except WatchFailure as failure:
            alerts.append(
                {"alias": alias, "kind": failure.reason, "error": failure.detail, **failure.extra}
            )
            continue
        alerts.extend(alerts_for(alias, state, threshold))
    if alerts:
        return {
            "wake_agent": True,
            "data": {"reason": "attention_needed", "checked": len(vehicles), "alerts": alerts},
        }
    return {"wake_agent": False, "data": {"reason": "all_clear", "checked": len(vehicles)}}


def evaluate(runner: Runner = default_runner, directory: Path | None = None) -> dict[str, Any]:
    try:
        return decide(runner, directory if directory is not None else ops_scripts_dir())
    except WatchFailure as failure:
        return {
            "wake_agent": True,
            "data": {"reason": failure.reason, "error": failure.detail, **failure.extra},
        }


def main() -> int:
    # outer-boundary-process-contract: the scheduler reads this script's stdout
    # JSON to decide whether to wake the agent and treats a non-zero exit or
    # invalid stdout as "do not wake". An unhandled exception here would
    # therefore silence the watch forever, so the catch-all emits a fail-open
    # wake payload (wake_agent: true) carrying the error — a bug surfaces as a
    # run, never as silent gating. Only Exception is caught; KeyboardInterrupt
    # and SystemExit still propagate.
    try:
        result = evaluate()
    except Exception as exc:  # noqa: BLE001 — outer-boundary-process-contract (see above)
        result = {
            "wake_agent": True,
            "data": {"reason": "precheck_error", "error": f"{type(exc).__name__}: {exc}"},
        }
        print(f"tessie-precheck: unexpected error, waking the agent: {exc!r}", file=sys.stderr)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
