#!/usr/bin/env python3
"""Run one co-shipped Tessie CLI from encoded argv, without shell evaluation.

Usage: tessie-argv.py BASE64URL
       tessie-argv.py --encode JSON_FILE
BASE64URL is unpadded URL-safe base64 of one UTF-8 JSON object with exactly
{script, argv}. script is tessie-vehicles, tessie-allowlist, tessie-read,
tessie-command, tessie-confirm, tessie-late or tessie-charge; argv is a list of strings.
Build JSON using a serializer in the caller's structured-data/code context, then encode it there.
Only the resulting [A-Za-z0-9_-] token enters a shell command. Never interpolate
the original alias, destination, tag or confirmation into shell source.

At most 32768 encoded characters, 64 arguments and 8192 characters per argument
are accepted. Invalid input exits 2 with no stdout and a fixed repair diagnostic.
Valid input execs the named sibling with this Python interpreter and inherited
native identity. Stdout, stderr and exit status are exactly the selected script's
documented contract, including planned/effect output for tessie-command. This
adapter grants no authority and does not bypass role, VIN or confirmation checks.
For encoding, write JSON_FILE with a structured file-write tool, not shell
interpolation. --encode reads at most 24576 bytes from a regular nonsymlink file,
validates the same closed input and prints {"base64url": "..."}; it executes no CLI.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import stat
import sys
from collections.abc import Sequence
from pathlib import Path

SCRIPTS = frozenset(
    {
        "tessie-vehicles",
        "tessie-allowlist",
        "tessie-read",
        "tessie-command",
        "tessie-confirm",
        "tessie-late",
        "tessie-charge",
    }
)
TOKEN = re.compile(r"[A-Za-z0-9_-]{1,32768}")
DIAGNOSTIC = (
    "tessie: invalid encoded argv; rebuild bounded UTF-8 JSON {script, argv}, "
    "encode it as unpadded base64url, and keep raw values out of shell source\n"
)


def decode_argv(token: str) -> tuple[Path, list[str]]:
    """Validate a closed script selection and literal argv; never evaluate text."""
    if not TOKEN.fullmatch(token):
        raise ValueError("input")
    try:
        raw = base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True)
        value = json.loads(raw.decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("input") from exc
    if (
        not isinstance(value, dict)
        or set(value) != {"script", "argv"}
        or not isinstance(value["script"], str)
        or value["script"] not in SCRIPTS
        or not isinstance(value["argv"], list)
        or len(value["argv"]) > 64
    ):
        raise ValueError("input")
    args = value["argv"]
    for arg in args:
        if not isinstance(arg, str) or len(arg) > 8192 or "\0" in arg:
            raise ValueError("input")
        try:
            arg.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise ValueError("input") from exc
    root = Path(__file__).resolve().parent
    if value["script"] in {"tessie-late", "tessie-charge"}:
        skill = "tessie-running-late" if value["script"] == "tessie-late" else "tessie-charge"
        native = Path("/home/node/.claude/skills") / ("tessl__" + skill)
        if native.exists() or native.is_symlink():
            root = native / "scripts"
        else:
            owner = Path(__file__).absolute().parents[1]
            if value["script"] == "tessie-charge" and not (
                owner.name == "tessie-ops" and owner.parent.name == "skills"
            ):
                raise ValueError("input")
            root = root.parents[1] / skill / "scripts"
        if not root.is_dir():
            raise ValueError("input")
        root = root.resolve()
    target = (root / (value["script"] + ".py")).resolve()
    if target.parent != root or not target.is_file():
        raise ValueError("input")
    return target, args


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if len(args) == 2 and args[0] == "--encode":
            fd = os.open(args[1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as stream:
                metadata = os.fstat(stream.fileno())
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 24576:
                    raise ValueError("input")
                raw = stream.read(24577)
            if len(raw) > 24576:
                raise ValueError("input")
            token = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
            decode_argv(token)
            print(json.dumps({"base64url": token}))
            return 0
        if len(args) != 1:
            raise ValueError("input")
        target, literal_args = decode_argv(args[0])
    except (ValueError, OSError):
        sys.stderr.write(DIAGNOSTIC)
        return 2
    try:
        os.execv(sys.executable, [sys.executable, str(target), *literal_args])
    except OSError:
        sys.stderr.write("tessie: cannot start the co-shipped CLI; reinstall the plugin\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
