#!/usr/bin/env python3
"""Fixed running-late host operations; no caller authority or outbound mail body.

Usage: tessie-late.py prepare --event-id ID --recipient MAILBOX
       tessie-late.py poll | status
       tessie-late.py cancel --proposal-id HEX64

prepare returns the complete host-built pre-event approval card (text/buttons);
it does not approve or dispatch. poll asks the native host to inspect only current
meeting drive blocks and send within its shared two-message budget. status reads
only bounded private counts and performs no provider/vehicle I/O. cancel revokes
recipient delegation without clearing any consumed slot. Every operation requires
the genuine registered main source; flags cannot grant it.

Stdout: one JSON object. Native failures: fixed stderr/nonzero, no raw provider
body or alternate route. No direct HTTP, role/context/path/receipt flags exist.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence

from late_ipc import call


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Event-bound native running-late workflow")
    parser.add_argument("operation", choices=("prepare", "poll", "status", "cancel"))
    parser.add_argument("--event-id")
    parser.add_argument("--recipient")
    parser.add_argument("--proposal-id")
    args = parser.parse_args(argv)
    fields = {
        k: v
        for k, v in (
            ("event_id", args.event_id),
            ("recipient", args.recipient),
            ("proposal_id", args.proposal_id),
        )
        if v is not None
    }
    expected = (
        {"event_id", "recipient"}
        if args.operation == "prepare"
        else {"proposal_id"}
        if args.operation == "cancel"
        else set()
    )
    if set(fields) != expected or any(
        not isinstance(v, str)
        or not v
        or len(v) > 512
        or any(ord(c) < 32 or ord(c) == 127 for c in v)
        for v in fields.values()
    ):
        parser.error(
            "supply only the exact operation identifiers; "
            "no role, body or receipt input is supported"
        )
    if args.proposal_id is not None and re.fullmatch(r"[a-f0-9]{64}", args.proposal_id) is None:
        parser.error("proposal-id must be the exact opaque host identifier")
    try:
        result = call(args.operation, fields)
    # outer-boundary-process-contract: callers treat invalid/missing JSON as an
    # unknown native outcome. Emit fixed stderr/nonzero; propagation could leak
    # private IPC/provider details and break the redacted output contract.
    except Exception:  # noqa: BLE001 — outer-boundary-process-contract
        print(
            "Running-late held. Verify the installed host contract and native owner source; "
            "preserve budgets and never replay uncertain delivery.",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
