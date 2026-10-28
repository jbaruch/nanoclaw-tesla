#!/usr/bin/env python3
"""Native host callback adapter: one exact claim ID, no command/data selectors.

The registered host executor owns output byte limits, deadline, process retirement
and JSON result validation. Replace this process with its fixed compiled host
consumer. Neither IPC, provider access nor approval logic belongs in this adapter.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def run(args: list[str]) -> None:
    if len(args) != 1 or re.fullmatch(r"[A-Za-z0-9_-]{22}", args[0]) is None:
        raise ValueError("Use the real native callback claim.")
    root = Path(os.environ.get("NANOCLAW_CALLBACK_HOST_ROOT", ""))
    node = Path(os.environ.get("NANOCLAW_CALLBACK_NODE", ""))
    if not root.is_absolute() or not node.is_absolute():
        raise ValueError("Restore the host-selected callback registration.")
    root = root.resolve(strict=True)
    target = root / "dist/host-plugins/tessie-late/callback-cli.js"
    if (
        target.is_symlink()
        or not target.is_file()
        or not target.resolve(strict=True).is_relative_to(root)
    ):
        raise ValueError("Install the regular contained native callback consumer.")
    os.chdir(root)
    os.execve(node, [str(node), str(target), args[0]], {**os.environ, "LOG_LEVEL": "warn"})


def main() -> int:
    try:
        run(sys.argv[1:])
    except (ValueError, RuntimeError, OSError):
        print(
            "Running-late callback held; restore the native host registration "
            "and preserve its private proposal.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
