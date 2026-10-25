#!/usr/bin/env python3
"""Cached, status-gated read of one allowlisted vehicle.

Usage: tessie-read.py KIND [--vehicle ALIAS_OR_VIN] [--include-location]
                      [--from EPOCH] [--to EPOCH] [--tag TAG]

KIND: status, state, battery, tire_pressure, firmware_alerts,
consumption_since_charge, last_idle_state, drives (any chat with a role);
location, drivers (owner chats only).

Probes `GET /{vin}/status` first, then reads Tessie's cached copy. Never calls
wake and never asks for a live (`use_cache=false`) read, so a sleeping car is
answered from cache and reported as {"vehicle_status": "asleep", "from_cache": true}.
Coordinates and street addresses are stripped from stdout unless the chat is an
owner chat AND `--include-location` is given; asking for it from any other chat is
refused (exit 4), never silently ignored. `--from/--to/--tag` apply to `drives` only.

Stdout (JSON): {"vehicle", "kind", "vehicle_status", "from_cache", "data",
"location_redacted"}. Exit codes: see tessie_core.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from tessie_actions import OWNER_READS, READ_KINDS, read_vehicle, resolve
from tessie_cli import Runtime, guarded
from tessie_core import EXIT_DENIED, TessieError, emit
from tessie_policy import ROLE_OWNER, ROLE_READ


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read cached Tessie vehicle data")
    parser.add_argument("kind", choices=READ_KINDS)
    parser.add_argument("--vehicle", help="alias or VIN; default vehicle when omitted")
    parser.add_argument(
        "--include-location",
        action="store_true",
        help="owner chats only: keep coordinates and addresses in the output",
    )
    parser.add_argument("--from", dest="from_epoch", type=int, help="drives: start, unix seconds")
    parser.add_argument("--to", dest="to_epoch", type=int, help="drives: end, unix seconds")
    parser.add_argument("--tag", help="drives: only drives with this tag")
    return parser


def main(argv: Sequence[str] | None = None, *, runtime: Runtime | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    query = {
        key: value
        for key, value in (("from", args.from_epoch), ("to", args.to_epoch), ("tag", args.tag))
        if value is not None
    }
    if query and args.kind != "drives":
        parser.error("--from/--to/--tag apply to the drives read only")
    rt = runtime if runtime is not None else Runtime()

    def body() -> int:
        allowlist = rt.load()
        needs_owner = args.kind in OWNER_READS or args.include_location
        purpose = "precise location or the drivers list" if needs_owner else f"reading {args.kind}"
        role = rt.authorize(allowlist, ROLE_OWNER if needs_owner else ROLE_READ, purpose)
        if args.kind == "location" and not args.include_location:
            raise TessieError(
                "location is precise by definition: re-run with --include-location from an "
                "owner chat",
                code="location_flag_required",
                exit_code=EXIT_DENIED,
            )
        vehicle = resolve(rt.client, allowlist, args.vehicle)
        result = read_vehicle(
            rt.client,
            vehicle,
            args.kind,
            include_location=args.include_location and role == ROLE_OWNER,
            query=query or None,
        )
        emit(result, rt.out)
        return 0

    return guarded(rt, body)


if __name__ == "__main__":
    sys.exit(main())
