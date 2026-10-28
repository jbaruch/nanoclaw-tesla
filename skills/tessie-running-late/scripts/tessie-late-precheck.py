#!/usr/bin/env python3
"""Every-three-minute native running-late poll; host owns actual notification sends.

On success emits wake_agent:false with bounded count metadata: the host already
owns each native dispatch and its delivery budget. Never ask the model to send an
additional lateness notice. On failure emits fixed stderr/nonzero and a false wake
payload; task/host failure monitoring owns repair, never another API or resend.
No event state, route, contact, context flag or approval is supplied by this script.
"""

from __future__ import annotations

import json
import sys

from late_ipc import call


def main() -> int:
    if len(sys.argv) != 1:
        print(
            "Running-late precheck takes no arguments; use only its fixed native poll.",
            file=sys.stderr,
        )
        return 2
    try:
        result = call("poll")
    # outer-boundary-process-contract: the scheduler treats invalid/missing JSON
    # as an unknown result. Emit structured false-wake plus fixed stderr/nonzero;
    # propagation can expose private transport details and break that contract.
    except Exception:  # noqa: BLE001 — outer-boundary-process-contract
        print(
            "Running-late poll held. Inspect native host/owner setup "
            "and retained delivery history; do not resend.",
            file=sys.stderr,
        )
        print(json.dumps({"wake_agent": False, "data": {"reason": "native_hold"}}))
        return 1
    print(json.dumps({"wake_agent": False, "data": {"reason": "host_dispatched", **result}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
