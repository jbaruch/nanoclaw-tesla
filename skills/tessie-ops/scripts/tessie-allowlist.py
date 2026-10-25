#!/usr/bin/env python3
"""Inspect the vehicle allowlist and resolve one vehicle without touching it.

Usage:
  tessie-allowlist.py show
  tessie-allowlist.py resolve [--vehicle ALIAS_OR_VIN]

`show` prints the validated allowlist as {"role", "default_vehicle", "vehicles":
[{"alias", "vin_suffix", "shared"}], "watch"} — never chat ids or full VINs.
`resolve` additionally checks Tessie's live inventory (one cached `GET /vehicles`)
and prints {"role", "vehicle": {"alias", "vin_suffix", "car_type"}} or fails with a
denied reason (exit 4). Read-only: this script never writes the allowlist and never
sends a command. Exit codes: see tessie_core.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from tessie_actions import resolve
from tessie_cli import Runtime, guarded
from tessie_core import emit
from tessie_policy import ROLE_READ, vin_suffix


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect the Tessie vehicle allowlist")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("show", help="print the validated allowlist (no chat ids, no full VINs)")
    resolve_parser = sub.add_parser("resolve", help="check one vehicle against live inventory")
    resolve_parser.add_argument("--vehicle", help="alias or VIN; default vehicle when omitted")
    return parser


def main(argv: Sequence[str] | None = None, *, runtime: Runtime | None = None) -> int:
    args = build_parser().parse_args(argv)
    rt = runtime if runtime is not None else Runtime()

    def body() -> int:
        allowlist = rt.load()
        role = rt.authorize(allowlist, ROLE_READ, "allowlist inspection")
        if args.action == "show":
            emit(
                {
                    "role": role,
                    "default_vehicle": allowlist.default_vehicle,
                    "vehicles": [
                        {"alias": v.alias, "vin_suffix": vin_suffix(v.vin), "shared": v.shared}
                        for v in allowlist.vehicles
                    ],
                    "watch": {"low_battery_percent": allowlist.low_battery_percent},
                },
                rt.out,
            )
            return 0
        vehicle = resolve(rt.client, allowlist, args.vehicle)
        emit(
            {
                "role": role,
                "vehicle": {
                    "alias": vehicle.alias,
                    "vin_suffix": vehicle.vin_suffix,
                    "car_type": vehicle.live.car_type,
                },
            },
            rt.out,
        )
        return 0

    return guarded(rt, body)


if __name__ == "__main__":
    sys.exit(main())
