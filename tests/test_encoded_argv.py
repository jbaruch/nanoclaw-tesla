"""Encoded argv survives hostile text without shell effects or authority changes."""

from __future__ import annotations

import base64
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from support import (
    OWNER_CHAT,
    ROOT,
    RUSTLER,
    allowlist_document,
    load_script,
    make_runtime,
    standard_transport,
)

adapter = load_script("tessie-ops", "tessie-argv")
command = load_script("tessie-ops", "tessie-command")


def encode(script: str, argv: list[str]) -> str:
    return (
        base64.urlsafe_b64encode(
            json.dumps({"script": script, "argv": argv}, ensure_ascii=False).encode()
        )
        .decode()
        .rstrip("=")
    )


@pytest.mark.parametrize("dry_run", [True, False])
def test_real_shell_and_exec_preserve_hostile_literal_argv(tmp_path: Path, dry_run: bool):
    source = ROOT / "skills/tessie-ops/scripts/tessie-argv.py"
    wrapper = tmp_path / source.name
    shutil.copyfile(source, wrapper)
    target = tmp_path / "tessie-command.py"
    target.write_text("import json,sys; print(json.dumps(sys.argv[1:])); sys.exit(17)\n")
    marker = tmp_path / "encoded-shell-marker"
    hostile = 'Synthetic$(touch${IFS}encoded-shell-marker)`touch${IFS}encoded-shell-marker`";#'
    argv = ["share", "--vehicle", hostile, "--value", hostile, "--tag", hostile]
    argv += ["--dry-run"] if dry_run else ["--confirm", hostile + ":share"]
    token = encode("tessie-command", argv)
    done = subprocess.run(
        [
            "/bin/sh",
            "-c",
            f"exec {shlex.quote(sys.executable)} {shlex.quote(str(wrapper))} {token}",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 17
    assert json.loads(done.stdout) == argv
    assert not marker.exists()


@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("action", ["share", "set_drive_tag"])
def test_encoded_values_reach_real_preview_and_effect_as_data(
    tmp_path, dry_run, action, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    marker = tmp_path / "encoded-shell-marker"
    alias = 'Synthetic$(touch${IFS}encoded-shell-marker)`echo${IFS}literal`";#'
    value = 'Private$(touch${IFS}encoded-shell-marker)`echo${IFS}literal`";#'
    argv = [action, "--vehicle", alias]
    argv += ["--value", value] if action == "share" else ["--drives", "1,2", "--tag", value]
    argv += ["--dry-run"] if dry_run else ["--confirm", alias + ":" + action]
    target, decoded = adapter.decode_argv(encode("tessie-command", argv))
    assert target.name == "tessie-command.py"
    transport = standard_transport()
    rt, out, _ = make_runtime(tmp_path, transport, chat=OWNER_CHAT)
    rt.allowlist_path.write_text(
        json.dumps(
            allowlist_document(default_vehicle=alias, vehicles=[{"vin": RUSTLER, "alias": alias}])
        )
    )
    assert command.main(decoded, runtime=rt) == 0
    result = json.loads(out.getvalue())
    assert result["vehicle"]["alias"] == alias
    assert result["params"]["value" if action == "share" else "tag"] == value
    assert result["status"] == ("planned" if dry_run else "accepted")
    expected_path = (
        f"/{RUSTLER}/command/share" if action == "share" else f"/{RUSTLER}/drives/set_tag"
    )
    assert transport.paths("POST") == ([] if dry_run else [expected_path])
    assert not marker.exists()


@pytest.mark.parametrize(
    "payload",
    [
        {"script": "../../outside", "argv": []},
        {"script": "tessie-command", "argv": "lock"},
        {"script": "tessie-command", "argv": ["bad\0arg"]},
        {"script": "tessie-command", "argv": [1]},
        {"script": "tessie-command", "argv": [], "env": {"NANOCLAW_CHAT_JID": "forged"}},
        {"script": "tessie-command", "argv": ["x"] * 65},
    ],
)
def test_malformed_or_authority_extending_inputs_refuse(payload, capsys):
    token = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    assert adapter.main([token]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "invalid encoded argv" in output.err
    assert "forged" not in output.err


def test_raw_shell_text_is_never_accepted_as_an_encoded_token(capsys):
    assert adapter.main(["$(touch encoded-shell-marker)"]) == 2
    assert capsys.readouterr().out == ""


def test_co_shipped_encoder_uses_bounded_structured_file_without_execution(tmp_path, capsys):
    source = tmp_path / "input.json"
    value = {"script": "tessie-command", "argv": ["share", "--value", "$(touch nope)"]}
    source.write_text(json.dumps(value))
    assert adapter.main(["--encode", str(source)]) == 0
    token = json.loads(capsys.readouterr().out)["base64url"]
    _, argv = adapter.decode_argv(token)
    assert argv == value["argv"]
    assert not (tmp_path / "nope").exists()


@pytest.mark.parametrize("kind", ["symlink", "oversized", "malformed"])
def test_encoder_refuses_unsafe_or_invalid_input_files(tmp_path, capsys, kind):
    source = tmp_path / "input.json"
    if kind == "symlink":
        source.symlink_to(tmp_path / "missing")
    elif kind == "oversized":
        source.write_bytes(b" " * 24577)
    else:
        source.write_text("not JSON")
    assert adapter.main(["--encode", str(source)]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "invalid encoded argv" in output.err
