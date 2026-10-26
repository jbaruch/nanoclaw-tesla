"""Shared Tessie REST client, error model and location redaction.

Imported by the `tessie-*.py` CLIs in this directory and nothing else; it is
a library, not an entry point. Every request goes through
`TessieClient`. Its production transport is native host IPC without HTTP fallback.
The host enforces protected VIN/chat policy and uses the existing normal OneCLI gateway.
The client:

- talks only to `TESSIE_BASE_URL` over fixed route templates — no caller
  supplies a URL, host or path;
- never sets an `Authorization` header and refuses token-bearing query
  parameters: the OneCLI gateway injects the vaulted credential on the wire
  (host pattern `api.tessie.com`), so the container never holds it;
- never follows redirects, so a hop to another host cannot carry the
  injected credential;
- makes exactly one attempt per call. Retry policy belongs to Tessie
  (`max_attempts`, capped at `MAX_COMMAND_ATTEMPTS`), never to this client.

Exit codes shared by every CLI: 0 success, 1 failure, 2 usage (argparse),
3 unconfirmed control, 4 denied by allowlist or chat authorization.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol, TextIO

TESSIE_BASE_URL = "https://api.tessie.com"
USER_AGENT = "nanoclaw-tesla/0.1"

READ_TIMEOUT_SECONDS = 30
# Tessie holds a command open until the car answers (wait_for_completion) and
# retries internally up to max_attempts; the client must outlast that.
COMMAND_TIMEOUT_SECONDS = 120
# Tessie documents max_attempts as 1..3; the overlay never asks for more and
# adds no retry loop of its own.
MAX_COMMAND_ATTEMPTS = 3

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_UNCONFIRMED = 3
EXIT_DENIED = 4

VIN_PATTERN = re.compile(r"^[A-Z0-9]{17}$")

# Fixed read routes. `{vin}` is substituted only with a validated VIN.
READ_ROUTES: dict[str, str] = {
    "vehicles": "/vehicles",
    "status": "/{vin}/status",
    "state": "/{vin}/state",
    "battery": "/{vin}/battery",
    "tire_pressure": "/{vin}/tire_pressure",
    "firmware_alerts": "/{vin}/firmware_alerts",
    "location": "/{vin}/location",
    "consumption_since_charge": "/{vin}/consumption_since_charge",
    "last_idle_state": "/{vin}/last_idle_state",
    "drives": "/{vin}/drives",
    "drivers": "/{vin}/drivers",
}
# Fixed write routes: the supported control surface plus the drive-tag writer.
# Wake, trunks, windows, homelink, remote start, honk, sentry, valet and the
# rest of Tessie's command list are deliberately absent (docs/command-surface.md).
COMMAND_OPS = (
    "lock",
    "unlock",
    "start_climate",
    "stop_climate",
    "set_temperatures",
    "start_charging",
    "stop_charging",
    "set_charge_limit",
    "share",
    "flash",
)
DRIVE_TAG_ROUTE = "/{vin}/drives/set_tag"

FORBIDDEN_QUERY_KEYS = frozenset({"access_token", "token", "api_key", "authorization"})
FORBIDDEN_HEADERS = frozenset({"authorization", "proxy-authorization", "x-api-key"})

_SECRET_SHAPES = re.compile(r"(?i)(bearer\s+\S+|access_token=\S+|token[\"':= ]+\S+)")
_RETRY_AFTER_SHAPE = re.compile(r"^[0-9A-Za-z ,:+\-]{1,40}$")


class TessieError(Exception):
    """A failure the CLI reports on stderr and maps to an exit code."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "failed",
        exit_code: int = EXIT_FAILED,
        http_status: int | None = None,
        retry_after: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.exit_code = exit_code
        self.http_status = http_status
        self.retry_after = retry_after


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes
    dispatched_at_epoch: float | None = None


class Transport(Protocol):
    def send(
        self,
        method: str,
        url: str,
        *,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> HttpResponse: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Returning None makes urllib raise the 3xx as an HTTPError instead of following it.
        return None


def make_opener(proxy_handler: urllib.request.ProxyHandler | None = None):
    """Build the opener: system proxy settings honoured, redirects refused."""
    handlers: list[Any] = [_NoRedirect()]
    if proxy_handler is not None:
        handlers.append(proxy_handler)
    return urllib.request.build_opener(*handlers)


class UrllibTransport:
    """Explicit synthetic/loopback fixture adapter; never selected by Runtime defaults."""

    def __init__(self, opener: urllib.request.OpenerDirector | None = None) -> None:
        self._opener = opener if opener is not None else make_opener()

    def send(
        self,
        method: str,
        url: str,
        *,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> HttpResponse:
        request = urllib.request.Request(url, data=body, method=method, headers=dict(headers))
        try:
            with self._opener.open(request, timeout=timeout) as response:
                return HttpResponse(
                    response.status, dict(response.headers.items()), response.read()
                )
        except urllib.error.HTTPError as exc:
            # 3xx (redirect refused) and 4xx/5xx arrive here; the status is the signal.
            return HttpResponse(exc.code, dict(exc.headers.items()), exc.read())
        except TimeoutError as exc:
            raise TessieError(
                f"Tessie request timed out after {timeout:g}s ({method} {_route_label(url)}) — "
                "the vehicle or Tessie is slow; check status and retry later, do not loop",
                code="timeout",
            ) from exc
        except (urllib.error.URLError, ConnectionError) as exc:
            raise TessieError(
                f"Tessie is unreachable ({method} {_route_label(url)}): {exc} — check the "
                "OneCLI gateway and network, then retry",
                code="network",
            ) from exc


def _route_label(url: str) -> str:
    """Path without VIN or query, for diagnostics that must not leak either."""
    path = urllib.parse.urlsplit(url).path
    return re.sub(r"/[A-Z0-9]{17}(?=/|$)", "/{vin}", path)


def _header(headers: Mapping[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def _scrub(text: str) -> str:
    return _SECRET_SHAPES.sub("[redacted]", text)[:200]


def _error_detail(body: bytes) -> str:
    """Short, scrubbed `error`/`message` text from an error body, if any."""
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ""
    if isinstance(payload, dict):
        for key in ("error", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return _scrub(value.strip())
    return ""


def failure_for(response: HttpResponse) -> TessieError:
    """Map a non-2xx response to an actionable, token-free TessieError."""
    status = response.status
    detail = _error_detail(response.body)
    suffix = f" — Tessie said: {detail}" if detail else ""
    retry_after = _header(response.headers, "Retry-After")
    if retry_after is not None and not _RETRY_AFTER_SHAPE.match(retry_after):
        retry_after = None
    if status == 401:
        message = (
            "Tessie rejected the credential (HTTP 401): the vaulted token is missing, expired "
            "or revoked. Create a new token at https://dash.tessie.com/settings/api and update "
            "the OneCLI secret 'Tessie API token' (docs/setup.md, Recovery)"
        )
    elif status == 403:
        message = (
            "Tessie denied access (HTTP 403): the token cannot reach this vehicle or the "
            "account lost access. Check the vehicle's access in the Tessie app (docs/setup.md)"
        )
    elif status == 404:
        message = (
            "Tessie does not know this vehicle or route (HTTP 404): re-run tessie-vehicles.py "
            "to confirm the vehicle is still on the account"
        )
    elif status == 408:
        message = (
            "Tessie timed out talking to the vehicle (HTTP 408): the car may be offline or "
            "asleep. Do not retry in a loop; read cached status instead"
        )
    elif status == 429:
        message = "Tessie rate limit reached (HTTP 429): stop and wait before the next call"
        if retry_after:
            message += f"; Retry-After: {retry_after}"
    elif 500 <= status < 600:
        message = f"Tessie failed upstream (HTTP {status}): no retry was attempted; try again later"
    elif 300 <= status < 400:
        message = (
            f"Tessie answered with a redirect (HTTP {status}); redirects are refused so the "
            "injected credential cannot leave api.tessie.com"
        )
    else:
        message = f"Tessie returned an unexpected status (HTTP {status})"
    return TessieError(
        message + suffix,
        code=f"http_{status}",
        http_status=status,
        retry_after=retry_after,
    )


def _query_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class TessieClient:
    """Single-attempt Tessie REST client over fixed routes."""

    def __init__(self, transport: Transport | None = None) -> None:
        if transport is None:
            from tessie_native import NativeTransport

            transport = NativeTransport()
        self._transport: Transport = transport
        self.last_dispatch_epoch: float | None = None

    @property
    def host_authority(self) -> bool:
        return getattr(self._transport, "host_authority", False) is True

    def host_policy(self) -> object:
        from tessie_native import NativeTransport

        if not isinstance(self._transport, NativeTransport):
            raise TessieError("Native host policy is required", code="host_contract")
        return self._transport.policy()

    def confirm_selection(self, confirmation: str) -> None:
        from tessie_native import NativeTransport

        if isinstance(self._transport, NativeTransport):
            self._transport.confirmation = confirmation

    def _build(self, route: str, vin: str | None, query: Mapping[str, object] | None) -> str:
        if "{vin}" in route:
            if vin is None or not VIN_PATTERN.match(vin):
                raise TessieError("internal error: route needs a validated VIN", code="bad_vin")
            route = route.replace("{vin}", vin)
        url = TESSIE_BASE_URL + route
        if query:
            for key in query:
                if key.lower() in FORBIDDEN_QUERY_KEYS:
                    raise TessieError(
                        f"refusing query parameter {key!r}: credentials are injected by the "
                        "OneCLI gateway, never sent by the client",
                        code="forbidden_query",
                    )
            url += "?" + urllib.parse.urlencode({k: _query_value(v) for k, v in query.items()})
        return url

    def _request(
        self,
        method: str,
        route: str,
        *,
        vin: str | None,
        query: Mapping[str, object] | None,
        json_body: Mapping[str, object] | None,
        timeout: float,
    ) -> Any:
        url = self._build(route, vin, query)
        headers: dict[str, str] = {"Accept": "application/json", "User-Agent": USER_AGENT}
        body: bytes | None = None
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        for name in headers:
            if name.lower() in FORBIDDEN_HEADERS:
                raise TessieError("internal error: forbidden header", code="forbidden_header")
        response = self._transport.send(method, url, body=body, headers=headers, timeout=timeout)
        self.last_dispatch_epoch = response.dispatched_at_epoch
        if not 200 <= response.status < 300:
            raise failure_for(response)
        try:
            return json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TessieError(
                f"Tessie returned a non-JSON body (HTTP {response.status}) for "
                f"{method} {route}; report this response shape",
                code="malformed_response",
            ) from exc

    def get(
        self, name: str, *, vin: str | None = None, query: Mapping[str, object] | None = None
    ) -> Any:
        return self._request(
            "GET",
            READ_ROUTES[name],
            vin=vin,
            query=query,
            json_body=None,
            timeout=READ_TIMEOUT_SECONDS,
        )

    def command(
        self,
        op: str,
        *,
        vin: str,
        params: Mapping[str, object] | None = None,
        max_attempts: int = MAX_COMMAND_ATTEMPTS,
    ) -> Any:
        if op not in COMMAND_OPS:
            raise TessieError(f"unsupported command {op!r}", code="unsupported_command")
        if not 1 <= max_attempts <= MAX_COMMAND_ATTEMPTS:
            raise TessieError(
                f"max_attempts must be 1..{MAX_COMMAND_ATTEMPTS}, got {max_attempts}",
                code="bad_max_attempts",
            )
        query: dict[str, object] = {"wait_for_completion": True, "max_attempts": max_attempts}
        query.update(params or {})
        return self._request(
            "POST",
            f"/{{vin}}/command/{op}",
            vin=vin,
            query=query,
            json_body=None,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )

    def set_drive_tag(self, *, vin: str, drives: str, tag: str | None) -> Any:
        body: dict[str, object] = {"drives": drives}
        if tag is not None:
            body["tag"] = tag
        return self._request(
            "POST",
            DRIVE_TAG_ROUTE,
            vin=vin,
            query=None,
            json_body=body,
            timeout=READ_TIMEOUT_SECONDS,
        )


# --- Location redaction -------------------------------------------------------

_COORDINATE_KEY = re.compile(r"(?i)(^|_)(lat|latitude|lng|lon|longitude|gps|heading)(_|$)|^native_")
_ADDRESS_KEY = re.compile(
    r"(?i)address|street|(^|_)location$|route_destination|^destination|^place"
)


def _is_location_key(key: str) -> bool:
    return bool(_COORDINATE_KEY.search(key) or _ADDRESS_KEY.search(key))


def redact_location(value: Any) -> tuple[Any, int]:
    """Drop coordinate and street-address keys recursively. Returns (clean, dropped)."""
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        dropped = 0
        for key, item in value.items():
            if _is_location_key(str(key)):
                dropped += 1
                continue
            cleaned, inner = redact_location(item)
            clean[key] = cleaned
            dropped += inner
        return clean, dropped
    if isinstance(value, list):
        items: list[Any] = []
        dropped = 0
        for item in value:
            cleaned, inner = redact_location(item)
            items.append(cleaned)
            dropped += inner
        return items, dropped
    return value, 0


# --- CLI plumbing -------------------------------------------------------------

Clock = Callable[[], float]


def emit(payload: Mapping[str, Any], out: TextIO) -> None:
    out.write(json.dumps(payload, sort_keys=False) + "\n")


def report_failure(error: TessieError, err: TextIO) -> int:
    """Write the diagnostic to stderr and return the exit code. No stdout, no token."""
    err.write(f"tessie: {error.message}\n")
    return error.exit_code
