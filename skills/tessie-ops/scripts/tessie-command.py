#!/usr/bin/env python3
"""Send one control to one allowlisted vehicle and report confirmed state.

Usage: tessie-command.py ACTION [--vehicle ALIAS_OR_VIN] [--dry-run]
                         [--confirm "ALIAS:ACTION"] [--max-attempts N]
                         [--temperature C] [--percent N] [--value TEXT] [--locale xx-XX]
                         [--drives IDS] [--tag TAG]

ACTION: lock, unlock, start_climate, stop_climate, set_temperatures (--temperature
15..28 °C), start_charging, stop_charging, set_charge_limit (--percent 50..100),
share (--value, optional --locale), flash, set_drive_tag (--drives, optional --tag).

Needs a control or owner chat. Two steps keep the vehicle and action explicit:
`--dry-run` resolves the vehicle and prints the plan (no request sent to the car); the
real run must pass `--confirm "<alias>:<action>"` echoing that plan exactly, else it is
refused (exit 4) and nothing is sent. The command goes out once with
`wait_for_completion=true` and `--max-attempts` (1..3, default 3, Tessie's own retry).
Wake is not a supported action, but Tessie may wake a sleeping car to run a control.

Stdout (JSON): {"vehicle", "action", "params", "tessie_result", "status", ...} where
status is confirmed | accepted | unconfirmed | failed. `{"result": true}` from Tessie is
acceptance only; "confirmed" needs a fresh cached readback of the changed field.
A failed readback preserves tessie_result=true and the command receipt, returns
unconfirmed with safe confirmation_error metadata, and never retries the control.
Exit codes: 0 confirmed/accepted/planned, 1 failed, 3 unconfirmed, 4 denied.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from tessie_actions import (
    build_params,
    confirmation_phrase,
    plan_for,
    resolve,
    run_command,
    run_drive_tag,
)
from tessie_cli import Runtime, guarded
from tessie_core import (
    COMMAND_OPS,
    EXIT_DENIED,
    EXIT_FAILED,
    EXIT_OK,
    EXIT_UNCONFIRMED,
    MAX_COMMAND_ATTEMPTS,
    TessieError,
    emit,
)
from tessie_policy import ROLE_CONTROL, norm_alias

DRIVE_TAG_ACTION = "set_drive_tag"
ACTIONS = (*COMMAND_OPS, DRIVE_TAG_ACTION)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send a confirmed Tessie control")
    parser.add_argument("action", choices=ACTIONS)
    parser.add_argument("--vehicle", help="alias or VIN; default vehicle when omitted")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, send nothing")
    parser.add_argument("--confirm", help='must equal "<alias>:<action>" from the plan')
    parser.add_argument("--max-attempts", type=int, default=MAX_COMMAND_ATTEMPTS)
    parser.add_argument("--temperature", type=float, help="set_temperatures: 15..28 °C")
    parser.add_argument("--percent", type=int, help="set_charge_limit: 50..100")
    parser.add_argument("--value", help="share: destination text")
    parser.add_argument("--locale", help="share: locale such as en-US")
    parser.add_argument("--drives", help="set_drive_tag: comma-separated drive ids")
    parser.add_argument("--tag", help="set_drive_tag: tag text")
    return parser


def main(argv: Sequence[str] | None = None, *, runtime: Runtime | None = None) -> int:
    args = build_parser().parse_args(argv)
    rt = runtime if runtime is not None else Runtime()

    def body() -> int:
        is_tag = args.action == DRIVE_TAG_ACTION
        if is_tag:
            if args.drives is None:
                raise TessieError("set_drive_tag requires --drives", code="bad_parameter")
            params: dict = {"drives": args.drives, "tag": args.tag}
        else:
            params = build_params(
                args.action,
                {
                    "temperature": args.temperature,
                    "percent": args.percent,
                    "value": args.value,
                    "locale": args.locale,
                },
            )
        allowlist = rt.load()
        rt.authorize(allowlist, ROLE_CONTROL, f"controlling a vehicle ({args.action})")
        vehicle = resolve(rt.client, allowlist, args.vehicle)
        plan = plan_for(vehicle, args.action, params)
        if args.dry_run:
            emit({"status": "planned", **plan}, rt.out)
            return EXIT_OK
        expected = confirmation_phrase(vehicle.alias, args.action)
        if args.confirm is None or norm_alias(args.confirm) != norm_alias(expected):
            raise TessieError(
                f"refusing {args.action} on {vehicle.alias!r} (…{vehicle.vin_suffix}) without "
                f'confirmation: re-run with --confirm "{expected}". Nothing was sent.',
                code="confirmation_required",
                exit_code=EXIT_DENIED,
            )
        if is_tag:
            outcome = run_drive_tag(rt.client, vehicle, drives=args.drives, tag=args.tag)
        else:
            outcome = run_command(
                rt.client,
                vehicle,
                args.action,
                params,
                max_attempts=args.max_attempts,
                now=rt.now,
            )
        emit(outcome, rt.out)
        status = outcome["status"]
        if status == "failed":
            rt.err.write(f"tessie: {args.action} was not accepted by Tessie (result false)\n")
            return EXIT_FAILED
        if status == "unconfirmed":
            rt.err.write(
                f"tessie: {args.action} was accepted but the vehicle state did not confirm it "
                f"({outcome.get('reason')}); do not report it as done or retry automatically. "
                "Inspect cached state before a new explicit request.\n"
            )
            return EXIT_UNCONFIRMED
        return EXIT_OK

    return guarded(rt, body)


if __name__ == "__main__":
    sys.exit(main())
