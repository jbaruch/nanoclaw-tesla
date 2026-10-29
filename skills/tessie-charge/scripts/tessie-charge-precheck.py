#!/usr/bin/env python3
"""Native poll for an explicitly owner-enrolled cadence; this file installs none.

The host owns controls and its single evening notice. Successful polls emit
wake_agent:false and bounded counts; never ask a model to send a second notice.
Failures emit false-wake plus fixed stderr/nonzero for task failure monitoring.
No state, policy, context flag, route or vehicle selection enters this wrapper.
"""

from __future__ import annotations

import json
import sys

from charge_ipc import call


def main() -> int:
    if len(sys.argv) != 1:
        print("Calendar charging precheck accepts no arguments.", file=sys.stderr)
        return 2
    try:
        result = call("poll")
        counts = {name: result[name] for name in ("changed", "held")}
        if any(type(value) is not int or not 0 <= value <= 100 for value in counts.values()):
            raise ValueError("Invalid native charging counts.")
    # outer-boundary-process-contract: the scheduler treats missing/invalid
    # precheck JSON as silent failure. Emit fixed false-wake JSON plus fixed
    # stderr/nonzero; propagation would omit that required envelope and could
    # hide the native failure. False-wake never requests a duplicate notice.
    except Exception:  # noqa: BLE001 — outer-boundary-process-contract
        print(
            "Calendar charging held; inspect native owner setup and retained intent.",
            file=sys.stderr,
        )
        print(json.dumps({"wake_agent": False, "data": {"reason": "native_hold"}}))
        return 1
    print(json.dumps({"wake_agent": False, "data": {"reason": "native_host", **counts}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
