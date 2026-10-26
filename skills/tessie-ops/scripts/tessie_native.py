"""Version-1 host Tessie IPC. Never sends HTTP or falls back to local authority.

The native host derives identity from the task directory, revalidates protected
VIN/role policy, uses the existing OneCLI gateway and owns provider dispatch.
Scratch files and process environment grant no provider or location authority.
"""

from __future__ import annotations

import json
import math
import os
import re
import stat
import time
import urllib.parse
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from tessie_core import EXIT_DENIED, HttpResponse, TessieError

MAX_REPLY_BYTES = 2 * 1024 * 1024
IPC_ROOT = Path("/workspace/ipc")
_REQUEST_ID = re.compile(r"^[a-f0-9]{32}$")


def unavailable(code: str = "host_unavailable") -> TessieError:
    return TessieError(
        "Tessie host authority is unavailable or denied. Ask the host owner to check "
        "the installed native contract, protected vehicle policy and existing OneCLI "
        "gateway. Do not retry a control automatically; no direct HTTP fallback exists.",
        code=code,
        exit_code=EXIT_DENIED,
    )


class NativeIPC:
    def __init__(
        self,
        root: Path = IPC_ROOT,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        request_id: Callable[[], str] = lambda: uuid.uuid4().hex,
    ) -> None:
        self.root, self.monotonic, self.sleep, self.request_id = root, monotonic, sleep, request_id

    def call(self, payload: object, timeout: float) -> dict[str, Any]:
        request_id = self.request_id()
        if not _REQUEST_ID.fullmatch(request_id):
            raise unavailable()
        session = os.environ.get("NANOCLAW_SESSION_NAME", "default")
        if session not in ("default", "maintenance"):
            raise unavailable()
        target = self.root / "tasks" / f"tessie-{request_id}.json"
        temporary = target.with_suffix(".tmp")
        reply = self.root / "input" / f"_script_result_{request_id}.json"
        data = {
            "type": "tessie_request",
            "requestId": request_id,
            "sessionName": session,
            "payload": payload,
        }
        try:
            # File publication matches the native task-file transport. A
            # request ID is never reused or automatically re-enqueued.
            fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.rename(temporary, target)
            end = self.monotonic() + timeout
            while self.monotonic() < end:
                try:
                    fd = os.open(reply, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                except FileNotFoundError:
                    self.sleep(0.05)
                    continue
                with os.fdopen(fd, "rb") as stream:
                    before = os.fstat(stream.fileno())
                    if (
                        not stat.S_ISREG(before.st_mode)
                        or before.st_nlink != 1
                        or before.st_size > MAX_REPLY_BYTES
                    ):
                        raise unavailable("host_reply")
                    raw = stream.read(MAX_REPLY_BYTES + 1)
                    after = os.fstat(stream.fileno())
                    current = reply.lstat()
                    if (
                        len(raw) > MAX_REPLY_BYTES
                        or (
                            before.st_dev,
                            before.st_ino,
                            before.st_size,
                            before.st_mtime_ns,
                            before.st_ctime_ns,
                        )
                        != (
                            after.st_dev,
                            after.st_ino,
                            after.st_size,
                            after.st_mtime_ns,
                            after.st_ctime_ns,
                        )
                        or (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino)
                    ):
                        raise unavailable("host_reply")
                parsed = json.loads(raw.decode("utf-8"))
                reply.unlink()
                if (
                    not isinstance(parsed, dict)
                    or parsed.get("schema_version") != 1
                    or isinstance(parsed.get("schema_version"), bool)
                ):
                    raise unavailable("host_contract")
                error = parsed.get("error")
                if error is not None:
                    # Native diagnostics are intentionally not echoed; never
                    # allow a malformed peer body to expose a credential/path.
                    raise unavailable("host_denied")
                if (
                    set(parsed) - {"schema_version", "status", "data", "dispatched_at_epoch"}
                    or not isinstance(parsed.get("status"), int)
                    or isinstance(parsed.get("status"), bool)
                    or not 100 <= parsed["status"] <= 599
                    or "data" not in parsed
                ):
                    raise unavailable("host_contract")
                return parsed
            raise unavailable("host_timeout")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise unavailable("host_transport") from exc


class NativeTransport:
    """Transport adapter for the deterministic client; URLs become fixed IPC data."""

    host_authority = True

    def __init__(self, ipc: NativeIPC | None = None) -> None:
        self.ipc = ipc if ipc is not None else NativeIPC()
        self.confirmation: str | None = None

    def policy(self) -> object:
        reply = self.ipc.call("policy", 40)
        if reply["status"] != 200:
            raise unavailable("host_policy")
        return reply["data"]

    def send(
        self,
        method: str,
        url: str,
        *,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> HttpResponse:
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https" or parts.netloc != "api.tessie.com" or parts.fragment:
            raise unavailable("host_route")
        pairs = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        if len(dict(pairs)) != len(pairs):
            raise unavailable("host_query")
        payload = {
            "schema_version": 1,
            "method": method,
            "path": parts.path,
            "query": dict(pairs),
            "body": json.loads(body) if body is not None else None,
            "confirmation": self.confirmation if method == "POST" else None,
        }
        reply = self.ipc.call(payload, timeout + 45)
        stamp = reply.get("dispatched_at_epoch")
        if (
            isinstance(stamp, bool)
            or not isinstance(stamp, (int, float))
            or not math.isfinite(stamp)
            or stamp < 0
        ):
            stamp = None
        return HttpResponse(reply["status"], {}, json.dumps(reply["data"]).encode("utf-8"), stamp)
