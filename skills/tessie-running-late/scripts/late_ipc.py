"""Fixed same-provider bridge to native running-late protocol1.

No HTTP, state store, recipient send or authority fallback exists in this consumer.
The host authenticates the actual IPC directory, owner/chat policy and callback.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

OPS = Path("/home/node/.claude/skills/tessl__tessie-ops/scripts")
DEV_OPS = Path(__file__).resolve().parents[2] / "tessie-ops" / "scripts"


def native_type() -> Any:
    directory = OPS if OPS.parent.exists() or OPS.parent.is_symlink() else DEV_OPS
    target = directory / "tessie_native.py"
    if not target.is_file() or not (directory / "tessie_core.py").is_file():
        raise ValueError(
            "Reinstall the complete nanoclaw-tesla provider before using running-late; "
            "no fallback transport exists."
        )
    # The native transport and its co-shipped dependency resolve together.
    import sys

    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    spec = importlib.util.spec_from_file_location("tessie_late_native", target)
    if spec is None or spec.loader is None:
        raise ValueError("Reinstall the native Tessie transport before using running-late.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.NativeIPC


def call(operation: str, fields: dict[str, str] | None = None) -> dict[str, Any]:
    if operation not in {"prepare", "poll", "status", "cancel"}:
        raise ValueError("Use one documented running-late operation.")
    expected = (
        {"event_id", "recipient"}
        if operation == "prepare"
        else {"proposal_id"}
        if operation == "cancel"
        else set()
    )
    values = fields or {}
    if set(values) != expected:
        raise ValueError("Supply only the documented event/recipient or proposal identifiers.")
    bridge = native_type()()
    bridge.message_type = "tessie_late_request"
    reply = bridge.call({"schema_version": 1, "operation": operation, **values}, 300)
    if reply["status"] != 200 or not isinstance(reply["data"], dict):
        raise ValueError(
            "Running-late host held the request; preserve its native proposal "
            "and delivery history before retrying."
        )
    return reply["data"]
