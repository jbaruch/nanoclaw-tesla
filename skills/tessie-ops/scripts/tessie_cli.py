"""Runtime wiring shared by the tessie-*.py CLIs.

`Runtime` carries everything a CLI touches outside its own arguments — the HTTP
client, the allowlist path, the chat-identity witness, the clock and the
streams — so tests substitute all of it and production uses the defaults.
Neither the allowlist path nor the witness path is reachable from a command
line or an environment variable.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from tessie_core import Clock, TessieClient, TessieError, report_failure
from tessie_policy import (
    ALLOWLIST_PATH,
    WITNESS_ENVIRON_PATH,
    Allowlist,
    authorize,
    load_allowlist,
)


@dataclass
class Runtime:
    client: TessieClient = field(default_factory=TessieClient)
    allowlist_path: Path = ALLOWLIST_PATH
    environ_path: Path = WITNESS_ENVIRON_PATH
    env: Mapping[str, str] | None = None
    now: Clock = time.time
    out: TextIO = field(default_factory=lambda: sys.stdout)
    err: TextIO = field(default_factory=lambda: sys.stderr)

    def load(self) -> Allowlist:
        return load_allowlist(self.allowlist_path)

    def authorize(self, allowlist: Allowlist, minimum: str, purpose: str) -> str:
        return authorize(allowlist, minimum, purpose, environ_path=self.environ_path, env=self.env)


def guarded(runtime: Runtime, body: Callable[[], int]) -> int:
    """Run a CLI body; map TessieError to stderr + exit code, let anything else propagate."""
    try:
        return body()
    except TessieError as error:
        return report_failure(error, runtime.err)
