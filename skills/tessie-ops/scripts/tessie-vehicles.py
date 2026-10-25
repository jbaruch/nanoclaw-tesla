#!/usr/bin/env python3
"""List the vehicles this chat may address.

Usage: tessie-vehicles.py [--include-denied]

Stdout (JSON): {"role": str, "vehicles": [{"alias", "vin_suffix", "car_type",
"access_type", "is_active"}], "denied": [...]}. `denied` is present only with
`--include-denied` and only for an owner chat: it lists every Tessie row that is
NOT addressable as {alias_or_suffix, access_type, is_active, denied_reason}.
Neither list carries coordinates or full VINs.

One cached `GET /vehicles`. Never wakes a vehicle. Exit codes: see tessie_core.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from tessie_actions import fetch_inventory
from tessie_cli import Runtime, guarded
from tessie_core import emit
from tessie_policy import ROLE_OWNER, ROLE_READ, denied_summary, eligible_entries, vin_suffix


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="List addressable Tessie vehicles")
    parser.add_argument(
        "--include-denied",
        action="store_true",
        help="owner chats only: also list vehicles that are not addressable, with the reason",
    )
    return parser


def main(argv: Sequence[str] | None = None, *, runtime: Runtime | None = None) -> int:
    args = build_parser().parse_args(argv)
    rt = runtime if runtime is not None else Runtime()

    def body() -> int:
        allowlist = rt.load()
        role = rt.authorize(
            allowlist, ROLE_OWNER if args.include_denied else ROLE_READ, "vehicle list"
        )
        inventory = fetch_inventory(rt.client)
        rows = []
        for entry in eligible_entries(allowlist, inventory):
            live = inventory[entry.vin]
            rows.append(
                {
                    "alias": entry.alias,
                    "vin_suffix": vin_suffix(entry.vin),
                    "car_type": live.car_type,
                    "access_type": live.access_type,
                    "is_active": live.is_active,
                }
            )
        payload: dict = {"role": role, "vehicles": rows}
        if args.include_denied:
            payload["denied"] = denied_summary(allowlist, inventory)
        emit(payload, rt.out)
        return 0

    return guarded(rt, body)


if __name__ == "__main__":
    sys.exit(main())
