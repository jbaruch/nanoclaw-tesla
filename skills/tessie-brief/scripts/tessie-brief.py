#!/usr/bin/env python3
"""Read-only vehicle brief; no arguments, provider fallback, polling or controls.

One schema1 summary with deterministic lines for proven conditions and separate
explicit unknown coverage. Empty lines means no PROVEN alert, not proof of a
healthy vehicle when coverage is partial. No wake, task, notice or journal write.
"""

from __future__ import annotations

import argparse
import json
import sys

from brief_ipc import call

MAX_PACKET_BYTES = 256 * 1024


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        result = call()
        encoded = json.dumps(
            {"wake_agent": False, "data": result}, ensure_ascii=False, allow_nan=False
        )
        if len(encoded.encode("utf-8")) > MAX_PACKET_BYTES:
            raise ValueError("Inspect the bounded vehicle brief packet.")
    # outer-boundary-process-contract: the gather treats invalid stdout/nonzero
    # as unavailable evidence. Emit a fixed repair diagnostic so propagation
    # cannot leak native provider/location/storage prose into the morning brief.
    except Exception:  # noqa: BLE001 — outer-boundary-process-contract
        print(
            "Vehicle brief unavailable. Inspect the installed read-only contracts, "
            "protected owner policy and cached source coverage; "
            "never wake a vehicle or retry a control for the brief.",
            file=sys.stderr,
        )
        return 1
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
