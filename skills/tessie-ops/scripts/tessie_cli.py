"""CLI wiring with native host authority and explicitly injectable fixtures.

Production loads policy through host IPC. An unavailable native contract never
falls back to an agent-writable file or direct HTTP. Tests explicitly inject a
transport, policy path, identity witness, clock and streams.
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
    parse_allowlist,
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
        if self.client.host_authority:
            return parse_allowlist(self.client.host_policy())
        return load_allowlist(self.allowlist_path)

    def authorize(self, allowlist: Allowlist, minimum: str, purpose: str) -> str:
        return authorize(allowlist, minimum, purpose, environ_path=self.environ_path, env=self.env)


def guarded(runtime: Runtime, body: Callable[[], int]) -> int:
    """Run a CLI body; map TessieError to stderr + exit code, let anything else propagate."""
    try:
        return body()
    except TessieError as error:
        return report_failure(error, runtime.err)
