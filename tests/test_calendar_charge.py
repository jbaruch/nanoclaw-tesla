"""Native IPC composition and closed consumer inputs; no provider or vehicle I/O."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

import charge_ipc
from support import ROOT, load_script

cli = load_script("tessie-charge", "tessie-charge")
precheck = load_script("tessie-charge", "tessie-charge-precheck")


def test_actual_native_ipc_publishes_one_charge_request_and_consumes_only_its_reply(
    tmp_path,
    monkeypatch,
):
    (tmp_path / "tasks").mkdir()
    (tmp_path / "input").mkdir()
    request_id = "00112233445566778899aabbccddeeff"
    elapsed = [0.0]
    observed = []
    expected = {
        "type": "tessie_charge_request",
        "requestId": request_id,
        "sessionName": "default",
        "payload": {"schema_version": 1, "operation": "status"},
    }
    status = {
        "schema_version": 1,
        "states": 0,
        "active": 0,
        "held": 0,
        "owner_overrides": 0,
        "provider_operations": 0,
    }

    def receive(seconds):
        elapsed[0] += seconds
        if observed:
            return
        task = tmp_path / "tasks" / f"tessie-{request_id}.json"
        observed.append(json.loads(task.read_text()))
        assert task.stat().st_mode & 0o777 == 0o600
        reply = {"schema_version": 1, "status": 200, "data": status}
        (tmp_path / "input" / f"_script_result_{request_id}.json").write_text(json.dumps(reply))

    native = charge_ipc.native_type()
    bridge = native(
        tmp_path, monotonic=lambda: elapsed[0], sleep=receive, request_id=lambda: request_id
    )
    monkeypatch.setenv("NANOCLAW_SESSION_NAME", "default")
    monkeypatch.setattr(charge_ipc, "native_type", lambda: lambda: bridge)
    assert charge_ipc.call("status") == status
    assert observed == [expected]
    assert not list((tmp_path / "tasks").glob("*.tmp"))
    assert not list((tmp_path / "input").iterdir())


@pytest.mark.parametrize(
    "fields",
    [
        {"owner_chat": "tg:owner"},
        {"approved": True},
        {"ready": True},
        {"baseline": 60},
        {"vin": "SYNTH000000000001"},
        {"route": "foreign"},
    ],
)
def test_scratch_data_cannot_extend_native_authority(fields, monkeypatch):
    def forbidden():
        pytest.fail("invalid inputs must not publish a native request")

    monkeypatch.setattr(charge_ipc, "native_type", forbidden)
    with pytest.raises(ValueError):
        charge_ipc.call("poll", fields)


@pytest.mark.parametrize(
    "change",
    [
        {"distance_km": -1},
        {"distance_km": float("inf")},
        {"distance_km": True},
        {"vehicle": ""},
        {"departure": "2024-02-30T08:00:00Z"},
        {"departure": "2024-01-16T08:00:00"},
        {"departure": "2024-01-16"},
    ],
)
def test_invalid_estimates_fail_before_ipc(change, monkeypatch):
    fields = {
        "vehicle": "Native car",
        "distance_km": 250,
        "departure": "2024-01-16T08:00:00Z",
        **change,
    }
    with pytest.raises(ValueError):
        charge_ipc.validate_input("estimate", fields)


def test_estimate_cli_keeps_literal_vehicle_and_uses_no_control_fields(monkeypatch, capsys):
    observed = []

    def invoke(operation, fields):
        observed.append((operation, fields))
        return {"schema_version": 1, "forecast_only": True}

    monkeypatch.setattr(cli, "call", invoke)
    vehicle = "Native $(no shell) car"
    assert (
        cli.main(
            [
                "estimate",
                "--vehicle",
                vehicle,
                "--distance-km",
                "250",
                "--departure",
                "2024-01-16T08:00:00Z",
            ]
        )
        == 0
    )
    assert observed == [
        (
            "estimate",
            {"vehicle": vehicle, "distance_km": 250.0, "departure": "2024-01-16T08:00:00Z"},
        )
    ]
    assert json.loads(capsys.readouterr().out)["forecast_only"] is True


@pytest.mark.parametrize(
    "args",
    [
        ["poll", "--approved"],
        ["poll", "--vehicle", "Native car"],
        ["status", "--role", "main"],
        ["estimate", "--vehicle", "Native car"],
    ],
)
def test_real_cli_rejects_authority_or_incomplete_inputs(args):
    done = subprocess.run(
        [sys.executable, str(ROOT / "skills/tessie-charge/scripts/tessie-charge.py"), *args],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert done.returncode == 2
    assert done.stdout == ""
    assert "Traceback" not in done.stderr


def test_unknown_native_outcome_never_retries_or_requests_a_model_notice(monkeypatch, capsys):
    calls = []

    def fail(*args):
        calls.append(args)
        raise RuntimeError("private-provider-value")

    monkeypatch.setattr(cli, "call", fail)
    assert cli.main(["poll"]) == 1
    first = capsys.readouterr()
    assert first.out == "" and "private-provider-value" not in first.err
    assert len(calls) == 1
    monkeypatch.setattr(precheck, "call", fail)
    monkeypatch.setattr(sys, "argv", ["precheck"])
    assert precheck.main() == 1
    second = capsys.readouterr()
    assert json.loads(second.out) == {"wake_agent": False, "data": {"reason": "native_hold"}}
    assert "private-provider-value" not in second.err
    assert len(calls) == 2


def test_successful_native_poll_is_quiet_and_cannot_return_a_duplicate_message(monkeypatch, capsys):
    monkeypatch.setattr(
        precheck,
        "call",
        lambda operation: {
            "schema_version": 1,
            "changed": 1,
            "held": 0,
            "notice": "submitted",
            "items": [{"kind": "raised", "vehicle": "Native car", "limit": 98, "stops": 0}],
        },
    )
    monkeypatch.setattr(sys, "argv", ["precheck"])
    assert precheck.main() == 0
    assert json.loads(capsys.readouterr().out) == {
        "wake_agent": False,
        "data": {"reason": "native_host", "changed": 1, "held": 0},
    }


@pytest.mark.parametrize(
    "reply",
    [
        {"status": 403, "data": {"schema_version": 1}},
        {"status": 200, "data": {"schema_version": True}},
        {"status": 200, "data": {"schema_version": 2}},
        {"status": 200, "data": []},
    ],
)
def test_missing_host_or_future_contract_is_held_without_alternate_route(reply, monkeypatch):
    class Peer:
        def call(self, payload, timeout):
            assert payload == {"schema_version": 1, "operation": "status"}
            assert timeout == 200
            return reply

    monkeypatch.setattr(charge_ipc, "native_type", lambda: Peer)
    with pytest.raises(ValueError):
        charge_ipc.call("status")


def test_nonfinite_native_result_is_a_fixed_cli_hold(monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "call", lambda *args: {"schema_version": 1, "unexpected": float("nan")}
    )
    assert cli.main(["status"]) == 1
    result = capsys.readouterr()
    assert result.out == ""
    assert "Traceback" not in result.err


@pytest.mark.parametrize("kind", ["missing", "symlink", "hardlink", "directory", "fifo"])
def test_present_incomplete_native_provider_never_uses_development_fallback(
    kind, tmp_path, monkeypatch
):
    scripts = tmp_path / "native/scripts"
    scripts.mkdir(parents=True)
    core = scripts / "tessie_core.py"
    core.write_text("# fixed incomplete native fixture")
    target = scripts / "tessie_native.py"
    outside = tmp_path / "retained-fixture"
    outside.write_text("# never imported")
    if kind == "symlink":
        target.symlink_to(outside)
    elif kind == "hardlink":
        target.hardlink_to(outside)
    elif kind == "directory":
        target.mkdir()
    elif kind == "fifo":
        import os

        os.mkfifo(target)
    monkeypatch.setattr(charge_ipc, "OPS", scripts)
    with pytest.raises((ValueError, OSError)):
        charge_ipc.native_type()
    assert outside.read_text() == "# never imported"
