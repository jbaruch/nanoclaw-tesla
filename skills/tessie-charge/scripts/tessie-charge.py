#!/usr/bin/env python3
"""Native calendar-charge poll/status or read-only reusable energy estimate.

Usage: tessie-charge.py poll | status
       tessie-charge.py estimate --vehicle ALIAS --distance-km NUMBER --departure RFC3339

Stdout is one native schema-1 JSON result. poll may invoke standing-owner-approved
controls and the host's one-evening notice. status has no provider I/O. estimate
reads measured vehicle/charging inputs but grants no control or approval. No
caller role, VIN list, route, policy, baseline, receipt or enrollment selector.
Failures emit fixed stderr/nonzero; no direct provider fallback or auto-retry.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from charge_ipc import call, validate_input


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Protected native calendar-aware charging")
    parser.add_argument("operation", choices=("poll", "status", "estimate"))
    parser.add_argument("--vehicle")
    parser.add_argument("--distance-km", type=float)
    parser.add_argument("--departure")
    args = parser.parse_args(argv)
    fields = {
        key: value
        for key, value in (
            ("vehicle", args.vehicle),
            ("distance_km", args.distance_km),
            ("departure", args.departure),
        )
        if value is not None
    }
    try:
        validate_input(args.operation, fields)
    except ValueError:
        parser.error("Use only the documented operation and bounded, zoned estimate inputs.")
    try:
        result = call(args.operation, fields)
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False)
    # outer-boundary-process-contract: this finite JSON CLI is an agent boundary.
    # Fixed stderr/nonzero retains the unknown native outcome without leaking
    # provider/storage prose. Never retry or manufacture a ready/approval flag.
    except Exception:  # noqa: BLE001 — outer-boundary-process-contract
        print(
            "Calendar charging held. Inspect installed host authority, native owner enrollment "
            "and retained control history; never replay an uncertain command.",
            file=sys.stderr,
        )
        return 1
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
