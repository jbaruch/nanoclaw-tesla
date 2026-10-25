"""Transport boundary: hardcoded host, no client credential, bounded retries, error mapping."""

from __future__ import annotations

import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from support import RUSTLER, FakeTransport, json_response
from tessie_core import (
    COMMAND_OPS,
    MAX_COMMAND_ATTEMPTS,
    READ_ROUTES,
    TESSIE_BASE_URL,
    HttpResponse,
    TessieClient,
    TessieError,
    UrllibTransport,
    failure_for,
    make_opener,
)


def client_for(routes) -> tuple[TessieClient, FakeTransport]:
    transport = FakeTransport(routes)
    return TessieClient(transport), transport


def test_every_request_targets_the_hardcoded_host_without_credentials() -> None:
    client, transport = client_for(
        {
            ("GET", "/vehicles"): json_response({"results": []}),
            ("GET", f"/{RUSTLER}/state"): json_response({}),
            ("POST", f"/{RUSTLER}/command/lock"): json_response({"result": True}),
        }
    )
    client.get("vehicles")
    client.get("state", vin=RUSTLER)
    client.command("lock", vin=RUSTLER)
    assert len(transport.calls) == 3
    for call in transport.calls:
        assert call["host"] == TESSIE_BASE_URL
        assert not {h.lower() for h in call["headers"]} & {"authorization", "x-api-key"}
        assert not {"access_token", "token"} & set(call["query"])


def test_client_refuses_token_bearing_query_parameters() -> None:
    client, transport = client_for({("GET", f"/{RUSTLER}/state"): json_response({})})
    with pytest.raises(TessieError) as caught:
        client.get("state", vin=RUSTLER, query={"access_token": "x"})
    assert caught.value.code == "forbidden_query"
    assert transport.calls == []


def test_vin_must_be_validated_before_it_reaches_a_path() -> None:
    client, transport = client_for({})
    with pytest.raises(TessieError) as caught:
        client.get("state", vin="../etc/passwd")
    assert caught.value.code == "bad_vin"
    assert transport.calls == []


def test_command_asks_tessie_to_wait_and_caps_attempts_at_three() -> None:
    client, transport = client_for(
        {("POST", f"/{RUSTLER}/command/lock"): json_response({"result": True})}
    )
    client.command("lock", vin=RUSTLER)
    call = transport.calls[0]
    assert call["query"] == {"wait_for_completion": "true", "max_attempts": "3"}
    assert MAX_COMMAND_ATTEMPTS == 3


@pytest.mark.parametrize("attempts", [0, 4, -1])
def test_max_attempts_above_three_or_below_one_is_refused(attempts: int) -> None:
    client, transport = client_for({})
    with pytest.raises(TessieError) as caught:
        client.command("lock", vin=RUSTLER, max_attempts=attempts)
    assert caught.value.code == "bad_max_attempts"
    assert transport.calls == []


def test_unsupported_commands_are_not_routable() -> None:
    client, transport = client_for({})
    for op in ("wake", "honk", "remote_start", "activate_front_trunk", "trigger_homelink"):
        with pytest.raises(TessieError) as caught:
            client.command(op, vin=RUSTLER)
        assert caught.value.code == "unsupported_command"
    assert transport.calls == []
    assert "wake" not in COMMAND_OPS
    assert "wake" not in READ_ROUTES


@pytest.mark.parametrize(
    ("status", "needle"),
    [
        (401, "revoked"),
        (403, "denied access"),
        (404, "does not know"),
        (408, "timed out talking to the vehicle"),
        (429, "rate limit"),
        (500, "upstream"),
        (503, "upstream"),
    ],
)
def test_http_failures_fail_closed_with_one_attempt_and_actionable_text(
    status: int, needle: str
) -> None:
    client, transport = client_for(
        {("GET", f"/{RUSTLER}/state"): json_response({"error": "nope"}, status=status)}
    )
    with pytest.raises(TessieError) as caught:
        client.get("state", vin=RUSTLER)
    assert caught.value.http_status == status
    assert needle in caught.value.message
    assert len(transport.calls) == 1  # no retry loop of our own
    assert RUSTLER not in caught.value.message


def test_rate_limit_surfaces_retry_after_without_looping() -> None:
    client, transport = client_for(
        {
            ("GET", f"/{RUSTLER}/state"): json_response(
                {}, status=429, headers={"Retry-After": "120"}
            )
        }
    )
    with pytest.raises(TessieError) as caught:
        client.get("state", vin=RUSTLER)
    assert caught.value.retry_after == "120"
    assert "Retry-After: 120" in caught.value.message
    assert len(transport.calls) == 1


def test_error_bodies_never_echo_secret_shaped_text() -> None:
    response = HttpResponse(
        401, {}, json.dumps({"error": "bad Bearer abc123SECRET and access_token=zzz"}).encode()
    )
    message = failure_for(response).message
    assert "abc123SECRET" not in message
    assert "zzz" not in message


def test_non_json_success_body_is_a_malformed_response() -> None:
    client, _ = client_for(
        {("GET", f"/{RUSTLER}/state"): HttpResponse(200, {}, b"<html>oops</html>")}
    )
    with pytest.raises(TessieError) as caught:
        client.get("state", vin=RUSTLER)
    assert caught.value.code == "malformed_response"


def test_drive_tag_posts_json_body_to_the_fixed_route() -> None:
    client, transport = client_for(
        {("POST", f"/{RUSTLER}/drives/set_tag"): json_response({"result": True})}
    )
    client.set_drive_tag(vin=RUSTLER, drives="1,2", tag="Business")
    call = transport.calls[0]
    assert json.loads(call["body"]) == {"drives": "1,2", "tag": "Business"}
    assert call["headers"]["Content-Type"] == "application/json"


# --- UrllibTransport against a loopback server (no Tessie, no real network) ----------


class _Recorder(BaseHTTPRequestHandler):
    seen: list[dict] = []

    def do_GET(self) -> None:  # noqa: N802 — http.server API
        _Recorder.seen.append({"path": self.path, "auth": self.headers.get("Authorization")})
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/landed")
            self.end_headers()
            return
        body = b'{"ok": true}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


@pytest.fixture
def loopback():
    _Recorder.seen = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Recorder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_transport_does_not_follow_redirects_and_sends_no_authorization(loopback: str) -> None:
    transport = UrllibTransport(make_opener(urllib.request.ProxyHandler({})))
    response = transport.send(
        "GET", loopback + "/redirect", body=None, headers={"Accept": "application/json"}, timeout=5
    )
    assert response.status == 302
    assert [s["path"] for s in _Recorder.seen] == ["/redirect"]  # /landed never requested
    assert all(s["auth"] is None for s in _Recorder.seen)
    assert "redirect" in failure_for(response).message


def test_transport_returns_success_bodies(loopback: str) -> None:
    transport = UrllibTransport(make_opener(urllib.request.ProxyHandler({})))
    response = transport.send("GET", loopback + "/ok", body=None, headers={}, timeout=5)
    assert response.status == 200
    assert json.loads(response.body) == {"ok": True}


class _TimeoutOpener(urllib.request.OpenerDirector):
    def open(self, fullurl, data=None, timeout=0):  # noqa: ANN001
        raise TimeoutError("simulated")


def test_transport_maps_timeouts_to_an_actionable_error() -> None:
    transport = UrllibTransport(_TimeoutOpener())
    with pytest.raises(TessieError) as caught:
        transport.send(
            "GET", f"{TESSIE_BASE_URL}/{RUSTLER}/state", body=None, headers={}, timeout=7
        )
    assert caught.value.code == "timeout"
    assert RUSTLER not in caught.value.message
    assert "do not loop" in caught.value.message
