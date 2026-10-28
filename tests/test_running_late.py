"""Native-only consumer contracts; no provider, vehicle or outbound effects."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import late_ipc
from support import ROOT, load_script

cli = load_script("tessie-running-late", "tessie-late")
precheck = load_script("tessie-running-late", "tessie-late-precheck")
callback = load_script("tessie-running-late", "tessie-late-callback-v1")
adapter = load_script("tessie-ops", "tessie-argv")


def test_closed_ipc_payload_uses_actual_native_transport_shape(monkeypatch):
    seen = []

    class Native:
        message_type = "tessie_request"

        def call(self, payload, timeout):
            seen.append((self.message_type, payload, timeout))
            return {"status": 200, "data": {"attempts": 0}}

    monkeypatch.setattr(late_ipc, "native_type", lambda: Native)
    assert late_ipc.call("status") == {"attempts": 0}
    assert seen == [("tessie_late_request", {"schema_version": 1, "operation": "status"}, 300)]
    with pytest.raises(ValueError):
        late_ipc.call("send", {"approved": "true"})
    with pytest.raises(ValueError):
        late_ipc.call("poll", {"receipt": "pretend"})
    assert len(seen) == 1


def test_cli_preserves_literal_event_and_recipient_without_body_or_approval(monkeypatch, capsys):
    calls = []

    def invoke(op, fields):
        calls.append((op, fields))
        return {"proposal_id": "1" * 64, "text": "Exact native card", "buttons": []}

    monkeypatch.setattr(cli, "call", invoke)
    assert (
        cli.main(
            ["prepare", "--event-id", "literal$(no shell)", "--recipient", "waiting@example.test"]
        )
        == 0
    )
    assert calls == [
        ("prepare", {"event_id": "literal$(no shell)", "recipient": "waiting@example.test"})
    ]
    assert json.loads(capsys.readouterr().out)["text"] == "Exact native card"


@pytest.mark.parametrize(
    "args",
    [
        ["poll", "--recipient", "waiting@example.test"],
        ["status", "--event-id", "event"],
        ["prepare", "--event-id", "event"],
        ["cancel", "--proposal-id", "invalid"],
        ["poll", "--approved"],
        ["poll", "--role", "main"],
        ["poll", "--receipt", "native-looking"],
    ],
)
def test_real_stdin_cli_cannot_extend_authority(args):
    done = subprocess.run(
        [sys.executable, str(ROOT / "skills/tessie-running-late/scripts/tessie-late.py"), *args],
        input="",
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 2
    assert done.stdout == ""
    assert "Traceback" not in done.stderr


def test_missing_native_reply_is_redacted_and_never_retried(monkeypatch, capsys):
    calls = []

    def fail(*args):
        calls.append(args)
        raise RuntimeError("private provider credential")

    monkeypatch.setattr(cli, "call", fail)
    assert cli.main(["status"]) == 1
    out = capsys.readouterr()
    assert out.out == "" and "private provider" not in out.err
    assert "preserve" in out.err and len(calls) == 1


def test_precheck_never_wakes_for_success_or_native_hold(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["precheck"])
    monkeypatch.setattr(
        precheck, "call", lambda _: {"owner_sent": 1, "recipient_sent": 1, "held": 0}
    )
    assert precheck.main() == 0
    assert json.loads(capsys.readouterr().out)["wake_agent"] is False

    def fail(_):
        raise RuntimeError("private body")

    monkeypatch.setattr(precheck, "call", fail)
    assert precheck.main() == 1
    out = capsys.readouterr()
    assert json.loads(out.out) == {"wake_agent": False, "data": {"reason": "native_hold"}}
    assert "private body" not in out.err
    monkeypatch.setattr(sys, "argv", ["precheck", "--approved"])
    assert precheck.main() == 2


def test_native_install_incomplete_refuses_developer_fallback(tmp_path, monkeypatch):
    native = tmp_path / "tessl__tessie-ops"
    native.mkdir()
    monkeypatch.setattr(late_ipc, "OPS", native / "scripts")
    with pytest.raises(ValueError, match="Reinstall"):
        late_ipc.native_type()


def test_literal_adapter_resolves_only_new_co_shipped_target():
    import base64

    payload = {"script": "tessie-late", "argv": ["cancel", "--proposal-id", "1" * 64]}
    token = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    target, args = adapter.decode_argv(token)
    assert target == ROOT / "skills/tessie-running-late/scripts/tessie-late.py"
    assert args == payload["argv"]


def test_callback_execs_only_fixed_compiled_host_consumer(tmp_path, monkeypatch):
    target = tmp_path / "dist/host-plugins/tessie-late/callback-cli.js"
    target.parent.mkdir(parents=True)
    target.write_text("fixed synthetic consumer")
    monkeypatch.setenv("NANOCLAW_CALLBACK_HOST_ROOT", str(tmp_path))
    monkeypatch.setenv("NANOCLAW_CALLBACK_NODE", sys.executable)
    observed = []

    def capture(executable, args, env):
        observed.append((executable, args, env["LOG_LEVEL"]))

    monkeypatch.setattr(callback.os, "execve", capture)
    monkeypatch.chdir(tmp_path)
    callback.run(["A" * 22])
    assert observed == [(Path(sys.executable), [sys.executable, str(target), "A" * 22], "warn")]
    with pytest.raises(ValueError):
        callback.run(["A" * 22, "--approved"])
    target.unlink()
    target.symlink_to(tmp_path / "elsewhere")
    with pytest.raises(ValueError):
        callback.run(["A" * 22])
    assert len(observed) == 1
