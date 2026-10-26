"""Native IPC fixtures only. No real provider, vault or vehicle operation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from support import NOW, OWNER_CHAT, RUSTLER, make_runtime, standard_transport, state_payload
from tessie_actions import resolve, run_command
from tessie_cli import Runtime
from tessie_core import HttpResponse, TessieClient, TessieError
from tessie_native import NativeIPC, NativeTransport, unavailable

ID = "00112233445566778899aabbccddeeff"


def ipc_fixture(tmp_path: Path, response: object):
    (tmp_path / "tasks").mkdir()
    (tmp_path / "input").mkdir()
    elapsed = [0.0]
    observed = []

    def sleep(seconds):
        elapsed[0] += seconds
        task = tmp_path / "tasks" / f"tessie-{ID}.json"
        if not observed:
            observed.append(json.loads(task.read_text()))
            assert task.stat().st_mode & 0o777 == 0o600
            (tmp_path / "input" / f"_script_result_{ID}.json").write_text(json.dumps(response))

    return NativeIPC(
        tmp_path, monotonic=lambda: elapsed[0], sleep=sleep, request_id=lambda: ID
    ), observed


def test_native_atomic_task_and_session_correlated_reply(tmp_path, monkeypatch):
    monkeypatch.setenv("NANOCLAW_SESSION_NAME", "maintenance")
    ipc, observed = ipc_fixture(
        tmp_path,
        {"schema_version": 1, "status": 200, "data": {"result": True}, "dispatched_at_epoch": NOW},
    )
    reply = ipc.call({"fixed": "synthetic"}, 1)
    assert reply["data"] == {"result": True}
    assert observed == [
        {
            "type": "tessie_request",
            "requestId": ID,
            "sessionName": "maintenance",
            "payload": {"fixed": "synthetic"},
        }
    ]
    assert not list((tmp_path / "tasks").glob("*.tmp"))
    assert not list((tmp_path / "input").iterdir())


@pytest.mark.parametrize(
    "reply",
    [
        {"schema_version": True, "status": 200, "data": {}},
        {"schema_version": 2, "status": 200, "data": {}},
        {"schema_version": 1, "status": True, "data": {}},
        {"schema_version": 1, "status": 200},
        {"schema_version": 1, "status": 200, "data": {}, "credential": "PRIVATE_SENTINEL"},
        {"schema_version": 1, "error": {"message": "PRIVATE_SENTINEL", "code": "denied"}},
    ],
)
def test_native_rejects_malformed_or_unsupported_contract_without_echo(tmp_path, reply):
    ipc, _ = ipc_fixture(tmp_path, reply)
    with pytest.raises(TessieError) as error:
        ipc.call("policy", 1)
    assert "PRIVATE_SENTINEL" not in str(error.value)


def test_timeout_enqueues_only_once_and_has_no_http_fallback(tmp_path):
    (tmp_path / "tasks").mkdir()
    (tmp_path / "input").mkdir()
    elapsed = [0.0]
    ipc = NativeIPC(
        tmp_path,
        monotonic=lambda: elapsed[0],
        sleep=lambda n: elapsed.__setitem__(0, elapsed[0] + n),
        request_id=lambda: ID,
    )
    with pytest.raises(TessieError, match="Do not retry"):
        ipc.call("policy", 0.1)
    assert len(list((tmp_path / "tasks").iterdir())) == 1


def test_unsupported_host_journal_is_actionable_without_echoing_peer_data(tmp_path):
    ipc, observed = ipc_fixture(
        tmp_path,
        {"schema_version": 1, "error": {"code": "journal_version", "message": "PRIVATE_SENTINEL"}},
    )
    with pytest.raises(TessieError) as error:
        ipc.call({"synthetic": "control"}, 1)
    assert error.value.code == "journal_version"
    assert "Update the host reader" in str(error.value)
    assert "Never delete the journal or replay" in str(error.value)
    assert "PRIVATE_SENTINEL" not in str(error.value)
    assert len(observed) == 1


def test_default_client_cannot_read_agent_writable_policy_or_fall_back(monkeypatch, tmp_path):
    # Even a permissive local file cannot replace a missing host contract.
    scratch = tmp_path / "allowlist.json"
    scratch.write_text('{"schema_version":1,"owner_chats":["tg:forged"],"vehicles":[]}')

    def missing(*args):
        raise unavailable()

    monkeypatch.setattr(NativeIPC, "call", missing)
    rt = Runtime(allowlist_path=scratch)
    assert rt.client.host_authority is True
    with pytest.raises(TessieError, match="host authority"):
        rt.load()


def test_transport_carries_fixed_request_and_host_dispatch_time_without_headers():
    class IPC:
        def __init__(self):
            self.calls = []

        def call(self, payload, timeout):
            self.calls.append((payload, timeout))
            return {
                "schema_version": 1,
                "status": 200,
                "data": {"result": True},
                "dispatched_at_epoch": NOW + 20,
            }

    ipc = IPC()
    transport = NativeTransport(ipc)  # type: ignore[arg-type]
    transport.confirmation = "Synthetic car:lock"
    result = transport.send(
        "POST",
        f"https://api.tessie.com/{RUSTLER}/command/lock?wait_for_completion=true&max_attempts=1",
        body=None,
        headers={"X-Private": "DO_NOT_FORWARD"},
        timeout=120,
    )
    assert result.dispatched_at_epoch == NOW + 20
    assert ipc.calls[0][0]["confirmation"] == "Synthetic car:lock"
    assert "DO_NOT_FORWARD" not in json.dumps(ipc.calls)
    with pytest.raises(TessieError):
        transport.send("POST", "https://evil.invalid/", body=None, headers={}, timeout=1)


@pytest.mark.parametrize(
    "host_stamp,reason", [(NOW + 30, "stale_state"), (None, "host_dispatch_time_unavailable")]
)
def test_confirmation_never_uses_pre_queue_client_time(tmp_path, host_stamp, reason):
    fake = standard_transport(state=state_payload(stamp_s=NOW + 15))
    original = fake.send

    def send(method, url, **kwargs):
        response = original(method, url, **kwargs)
        return HttpResponse(
            response.status,
            response.headers,
            response.body,
            host_stamp if method == "POST" else None,
        )

    fake.send = send

    class NativeFixtureClient(TessieClient):
        @property
        def host_authority(self) -> bool:
            return True

    client = NativeFixtureClient(fake)
    # Fixture policy remains explicitly injected; no production file lookup.
    rt, _, _ = make_runtime(tmp_path, chat=OWNER_CHAT, transport=standard_transport())
    allowed = rt.load()
    vehicle = resolve(client, allowed, "The Rustler")
    outcome = run_command(client, vehicle, "lock", {}, max_attempts=1, now=lambda: NOW)
    assert outcome["tessie_result"] is True
    assert outcome["status"] == "unconfirmed"
    assert outcome["reason"] == reason
    assert len(fake.paths("POST")) == 1
