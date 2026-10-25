#!/usr/bin/env python3
"""Read a vehicle's cached state back against what a control should have changed.

Usage: tessie-confirm.py ACTION --since EPOCH [--vehicle ALIAS_OR_VIN]
                         [--temperature C] [--percent N]

ACTION: lock, unlock, start_climate, stop_climate, set_temperatures,
start_charging, stop_charging, set_charge_limit. `--since` is the unix time the
control was sent (tessie-command.py prints it as sent_at); a state section older
than that, less the freshness slack, is stale and reads `unconfirmed`.

Stdout (JSON): {"vehicle", "action", "status", "reason", "field", "expected",
"observed", "state_timestamp"}. One cached `GET /vehicles` and `GET /state`; no wake.
Exit codes: 0 confirmed, 3 unconfirmed, 4 denied, 1 failure.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from tessie_actions import COMMAND_SPECS, build_params, confirm_state, resolve
from tessie_cli import Runtime, guarded
from tessie_core import EXIT_OK, EXIT_UNCONFIRMED, emit
from tessie_policy import ROLE_READ

STATEFUL_ACTIONS = tuple(op for op, spec in COMMAND_SPECS.items() if spec.section is not None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Confirm a Tessie control against vehicle state")
    parser.add_argument("action", choices=STATEFUL_ACTIONS)
    parser.add_argument(
        "--since", type=float, required=True, help="control sent time, unix seconds"
    )
    parser.add_argument("--vehicle", help="alias or VIN; default vehicle when omitted")
    parser.add_argument("--temperature", type=float, help="set_temperatures: 15..28 °C")
    parser.add_argument("--percent", type=int, help="set_charge_limit: 50..100")
    return parser


def main(argv: Sequence[str] | None = None, *, runtime: Runtime | None = None) -> int:
    args = build_parser().parse_args(argv)
    rt = runtime if runtime is not None else Runtime()

    def body() -> int:
        params = build_params(
            args.action, {"temperature": args.temperature, "percent": args.percent}
        )
        allowlist = rt.load()
        rt.authorize(allowlist, ROLE_READ, f"confirming {args.action}")
        vehicle = resolve(rt.client, allowlist, args.vehicle)
        result = confirm_state(rt.client, vehicle, args.action, params, since_epoch=args.since)
        emit(
            {
                "vehicle": {"alias": vehicle.alias, "vin_suffix": vehicle.vin_suffix},
                "action": args.action,
                **result,
            },
            rt.out,
        )
        return EXIT_OK if result["status"] == "confirmed" else EXIT_UNCONFIRMED

    return guarded(rt, body)


if __name__ == "__main__":
    sys.exit(main())
