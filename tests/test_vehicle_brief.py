"""Fixed read-only summary evidence and real native transport composition."""

from __future__ import annotations

import copy
import json

import pytest

import brief_ipc
from support import load_script

cli = load_script("tessie-brief", "tessie-brief")


def summary():
    return {
        "schema_version": 1,
        "day": "2020-01-02",
        "home_timezone": "America/Chicago",
        "observed_at": "2020-01-02T13:00:00.000Z",
        "checked_vehicles": 1,
        "coverage": "partial",
        "uncovered_sources": ["firmware_active_status"],
        "vehicles": [{"alias": "Synthetic Car", "alerts": [], "unknown_checks": []}],
    }


def test_healthy_supported_checks_have_no_lines_and_do_not_claim_unknown_firmware_is_healthy():
    result = brief_ipc.project(summary())
    assert result["lines"] == []
    assert result["coverage"] == "partial"
    assert result["uncovered_sources"] == ["firmware_active_status"]


def test_four_real_conditions_form_one_vehicle_line_and_no_model_inference():
    value = summary()
    value["vehicles"][0]["alerts"] = [
        {
            "kind": "overnight_unplugged",
            "detail": {
                "battery_percent": 20,
                "daily_limit_percent": 80,
                "samples": 331,
                "start": "2020-01-02T02:00:00.000Z",
                "end": "2020-01-02T13:00:00.000Z",
            },
        },
        {
            "kind": "insufficient_charge",
            "detail": {
                "shortfall_kwh": 20.4,
                "expected_departure_percent": 20,
                "required_percent": 55,
                "drive_count": 2,
            },
        },
        {"kind": "tire_warning", "detail": {"positions": ["rear_left"]}},
        {"kind": "open_vehicle_alert", "detail": {"flags": ["not_enough_power_to_heat"]}},
    ]
    result = brief_ipc.project(value)
    assert len(result["lines"]) == 1
    line = result["lines"][0]
    assert line.startswith("Synthetic Car: ")
    assert "сохранённым ночным наблюдениям" in line
    assert "20.4 кВт·ч" in line
    assert "заднее левое" in line
    assert "прогрева батареи" in line
    assert value == {key: result[key] for key in value}


@pytest.mark.parametrize(
    "change",
    [
        "future-version",
        "false-healthy",
        "foreign-zone",
        "missing-row",
        "private-field",
        "unknown-alert",
        "history-is-open",
        "duplicate-kind",
        "contradiction",
    ],
)
def test_malformed_or_unsupported_native_evidence_refuses(change):
    value = summary()
    if change == "future-version":
        value["schema_version"] = 2
    if change == "false-healthy":
        value["coverage"] = "complete"
    if change == "foreign-zone":
        value["day"] = "2020-01-01"
    if change == "missing-row":
        value["vehicles"] = []
    if change == "private-field":
        value["vehicles"][0]["vin"] = "SYNTHETIC"
    if change in ("unknown-alert", "history-is-open"):
        value["vehicles"][0]["alerts"] = [
            {"kind": "open_vehicle_alert", "detail": {"flags": ["old_firmware_history"]}}
        ]
    if change in ("duplicate-kind", "contradiction"):
        alert = {"kind": "tire_warning", "detail": {"positions": ["front_left"]}}
        value["vehicles"][0]["alerts"] = (
            [alert, copy.deepcopy(alert)] if change == "duplicate-kind" else [alert]
        )
        if change == "contradiction":
            value["vehicles"][0]["unknown_checks"] = ["tire_warning"]
    with pytest.raises(ValueError):
        brief_ipc.project(value)


def test_actual_native_transport_emits_only_one_fixed_summary_request(tmp_path, monkeypatch):
    (tmp_path / "tasks").mkdir()
    (tmp_path / "input").mkdir()
    rid = "00112233445566778899aabbccddeeff"
    elapsed, requests = [0.0], []
    native = brief_ipc.native_type()

    def receive(seconds):
        elapsed[0] += seconds
        if requests:
            return
        request = tmp_path / "tasks" / f"tessie-{rid}.json"
        requests.append(json.loads(request.read_text()))
        (tmp_path / "input" / f"_script_result_{rid}.json").write_text(
            json.dumps({"schema_version": 1, "status": 200, "data": summary()})
        )

    bridge = native(tmp_path, monotonic=lambda: elapsed[0], sleep=receive, request_id=lambda: rid)
    monkeypatch.setenv("NANOCLAW_SESSION_NAME", "default")
    monkeypatch.setattr(brief_ipc, "native_type", lambda: lambda: bridge)
    assert brief_ipc.call()["lines"] == []
    assert requests == [
        {
            "type": "tessie_brief_request",
            "requestId": rid,
            "sessionName": "default",
            "payload": {"schema_version": 1, "operation": "summary"},
        }
    ]
    assert not list((tmp_path / "input").iterdir())


def test_cli_no_effect_envelope_and_safe_failure(monkeypatch, capsys):
    monkeypatch.setattr(cli, "call", lambda: brief_ipc.project(summary()))
    monkeypatch.setattr("sys.argv", ["tessie-brief.py"])
    assert cli.main() == 0
    assert json.loads(capsys.readouterr().out)["wake_agent"] is False

    def fail():
        raise ValueError("private provider location token")

    monkeypatch.setattr(cli, "call", fail)
    assert cli.main() == 1
    result = capsys.readouterr()
    assert result.out == ""
    assert "private provider" not in result.err
    assert "never wake" in result.err


def test_paired_missing_home_retains_only_independent_warning_lines():
    value = summary()
    value.update(day=None, home_timezone=None)
    value["vehicles"][0]["unknown_checks"] = ["overnight_unplugged", "insufficient_charge"]
    value["vehicles"][0]["alerts"] = [
        {"kind": "tire_warning", "detail": {"positions": ["rear_right"]}}
    ]
    assert len(brief_ipc.project(value)["lines"]) == 1
    with pytest.raises(ValueError):
        brief_ipc.project({**value, "home_timezone": "America/Chicago"})
    value["vehicles"][0]["unknown_checks"] = []
    with pytest.raises(ValueError):
        brief_ipc.project(value)


def test_complete_hundred_vehicle_packet_fits_every_fixed_reply_boundary():
    value = summary()
    value["checked_vehicles"] = 100
    template = {
        "alias": "",
        "unknown_checks": [],
        "alerts": [
            {
                "kind": "overnight_unplugged",
                "detail": {
                    "battery_percent": 20,
                    "daily_limit_percent": 80,
                    "samples": 541,
                    "start": "2020-01-02T02:00:00.000Z",
                    "end": "2020-01-02T13:00:00.000Z",
                },
            },
            {
                "kind": "insufficient_charge",
                "detail": {
                    "shortfall_kwh": 20.4,
                    "expected_departure_percent": 20,
                    "required_percent": 55,
                    "drive_count": 2,
                },
            },
            {
                "kind": "tire_warning",
                "detail": {"positions": ["front_left", "front_right", "rear_left", "rear_right"]},
            },
            {"kind": "open_vehicle_alert", "detail": {"flags": ["not_enough_power_to_heat"]}},
        ],
    }
    value["vehicles"] = [
        {**copy.deepcopy(template), "alias": "車" * 96 + f"{index:03d}"} for index in range(100)
    ]
    assert len(json.dumps(value, ensure_ascii=False).encode()) < 128 * 1024
    projected = brief_ipc.project(value)
    assert len(projected["lines"]) == 100
    encoded = json.dumps({"wake_agent": False, "data": projected}, ensure_ascii=False).encode()
    assert 128 * 1024 < len(encoded) < 256 * 1024


def test_cli_refuses_oversized_rendered_output_without_partial_stdout(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["tessie-brief.py"])
    monkeypatch.setattr(cli, "call", lambda: {"lines": ["x" * (256 * 1024)]})
    assert cli.main() == 1
    assert capsys.readouterr().out == ""


def test_alias_bound_matches_native_hundred_utf16_units():
    value = summary()
    value["vehicles"][0]["alias"] = "🚗" * 50
    assert brief_ipc.project(value)["vehicles"][0]["alias"] == "🚗" * 50
    value["vehicles"][0]["alias"] += "🚗"
    with pytest.raises(ValueError):
        brief_ipc.project(value)


@pytest.mark.parametrize(
    ("amount", "rendered"),
    [
        (1.1, "1.1"),
        (0.3, "0.3"),
        (20.4, "20.4"),
        (2, "2"),
        (1.7000000000000002, "1.8"),
        (1.9000000000000001, "2"),
        (0.000000001, "0.1"),
        (10000000, "10000000"),
    ],
)
def test_decimal_ceiling_of_native_json_shortfall_preserves_original_evidence(amount, rendered):
    value = summary()
    value["vehicles"][0]["alerts"] = [
        {
            "kind": "insufficient_charge",
            "detail": {
                "shortfall_kwh": amount,
                "expected_departure_percent": 20,
                "required_percent": 55,
                "drive_count": 1,
            },
        }
    ]
    # Validate the actual native JSON number, without inferred epsilon/noise cleanup.
    wire = json.loads(json.dumps(value, allow_nan=False))
    original = copy.deepcopy(wire)
    result = brief_ipc.project(wire)
    assert result["lines"] == [
        f"Synthetic Car: по оценке на сегодняшние поездки не хватает {rendered} кВт·ч."
    ]
    assert {key: result[key] for key in original} == original


def _installed_provider(tmp_path, monkeypatch):
    import sys
    from pathlib import Path

    owner = load_script("tessie-brief", "brief_ipc")
    repo = Path(__file__).resolve().parents[1]
    provider = tmp_path / "provider/nanoclaw-tesla"
    skills = tmp_path / "native/skills"
    targets = (
        "skills/tessie-brief/scripts/tessie-brief.py",
        "skills/tessie-brief/scripts/brief_ipc.py",
        "skills/tessie-charge/scripts/charge_ipc.py",
        "skills/tessie-ops/scripts/tessie_native.py",
        "skills/tessie-ops/scripts/tessie_core.py",
    )
    fake = (
        "class NativeStub:\n    message_type = 'tessie_request'\n"
        "    def __init__(self, *args, **kwargs): pass\n"
        "    def call(self, payload, timeout): return "
        + repr({"schema_version": 1, "status": 200, "data": summary()})
        + "\ndef native_type(): return NativeStub\n"
    )
    for relative in (
        ".tessl-plugin/plugin.json",
        "rules/vehicle-brief-policy.md",
        "skills/tessie-brief/references/host-contract.md",
        "skills/tessie-brief/SKILL.md",
        *targets,
    ):
        file = provider / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes((repo / relative).read_bytes())
        if relative in targets:
            _, skill, *parts = Path(relative).parts
            native = skills / ("tessl__" + skill) / Path(*parts)
            native.parent.mkdir(parents=True, exist_ok=True)
            if relative.endswith("charge_ipc.py"):
                file.write_text(fake)
            native.write_bytes(file.read_bytes())
    monkeypatch.setattr(owner, "__file__", str(skills / "tessl__tessie-brief/scripts/brief_ipc.py"))
    monkeypatch.setattr(owner, "PROVIDER", provider, raising=False)
    monkeypatch.setattr(owner, "INSTALLED", skills / "tessl__tessie-charge/scripts")
    monkeypatch.setattr(sys, "path", list(sys.path))
    return owner, provider, skills


def test_complete_installed_provider_retains_fixed_summary_without_fallback(tmp_path, monkeypatch):
    owner, _, _ = _installed_provider(tmp_path, monkeypatch)
    assert owner.call()["lines"] == []


@pytest.mark.parametrize(
    "change",
    [
        "linked-scripts",
        "linked-skill",
        "wrong-provider",
        "heading-rule",
        "changed-copy",
        "hardlinked-target",
    ],
)
def test_installed_transport_refuses_substitutions_before_import(tmp_path, monkeypatch, change):
    owner, provider, skills = _installed_provider(tmp_path, monkeypatch)
    charge = skills / "tessl__tessie-charge/scripts/charge_ipc.py"
    if change in {"linked-scripts", "linked-skill"}:
        directory = charge.parent if change == "linked-scripts" else charge.parent.parent
        moved = tmp_path / "outside"
        directory.rename(moved)
        directory.symlink_to(moved, target_is_directory=True)
    if change == "wrong-provider":
        file = provider / ".tessl-plugin/plugin.json"
        value = json.loads(file.read_text())
        value["name"] = "jbaruch/impostor"
        file.write_text(json.dumps(value))
    if change == "heading-rule":
        (provider / "rules/vehicle-brief-policy.md").write_text("# Read-only brief\n")
    if change == "changed-copy":
        charge.write_text(charge.read_text() + "\n# replaced native copy\n")
    if change == "hardlinked-target":
        (tmp_path / "second.py").hardlink_to(charge)

    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid source must refuse before import")

    monkeypatch.setattr(owner.importlib.util, "spec_from_file_location", forbidden)
    with pytest.raises(ValueError):
        owner.native_type()


def test_provider_replacement_between_snapshot_and_import_refuses_before_execution(
    tmp_path, monkeypatch
):
    owner, provider, _ = _installed_provider(tmp_path, monkeypatch)
    original = owner.importlib.util.module_from_spec

    def replace(spec):
        module = original(spec)
        file = provider / ".tessl-plugin/plugin.json"
        value = json.loads(file.read_text())
        value["version"] = "0.5.1"
        file.write_text(json.dumps(value))
        return module

    monkeypatch.setattr(owner.importlib.util, "module_from_spec", replace)
    with pytest.raises(ValueError):
        owner.native_type()


def test_provider_change_during_native_type_resolution_refuses_before_bridge(tmp_path, monkeypatch):
    owner, provider, skills = _installed_provider(tmp_path, monkeypatch)
    relative = "skills/tessie-charge/scripts/charge_ipc.py"
    charge = skills / "tessl__tessie-charge/scripts/charge_ipc.py"
    mutation = (
        "\nfrom pathlib import Path\noriginal=native_type\ndef native_type():\n    p=Path("
        + repr(str(provider / ".tessl-plugin/plugin.json"))
        + ")\n    p.write_text(p.read_text().replace('0.5.0','0.5.1'))\n    return original()\n"
    )
    charge.write_text(charge.read_text() + mutation)
    (provider / relative).write_bytes(charge.read_bytes())
    with pytest.raises(ValueError):
        owner.native_type()


def test_provider_change_during_one_readback_holds_without_retry(tmp_path, monkeypatch):
    owner, provider, skills = _installed_provider(tmp_path, monkeypatch)
    charge = skills / "tessl__tessie-charge/scripts/charge_ipc.py"
    count = tmp_path / "attempts"
    mutation = (
        "\nfrom pathlib import Path\noriginal_call=NativeStub.call\n"
        "def changed_call(self,payload,timeout):\n"
        "    counter=Path(" + repr(str(count)) + ")\n"
        "    with counter.open('a') as output: output.write('1\\n')\n"
        "    result=original_call(self,payload,timeout)\n"
        "    p=Path(" + repr(str(provider / ".tessl-plugin/plugin.json")) + ")\n"
        "    p.write_text(p.read_text().replace('0.5.0','0.5.1'))\n"
        "    return result\nNativeStub.call=changed_call\n"
    )
    charge.write_text(charge.read_text() + mutation)
    (provider / "skills/tessie-charge/scripts/charge_ipc.py").write_bytes(charge.read_bytes())
    bridge = owner.native_type()()
    bridge.message_type = "tessie_brief_request"
    with pytest.raises(ValueError):
        bridge.call({"schema_version": 1, "operation": "summary"}, 200)
    assert count.read_text() == "1\n"


@pytest.mark.parametrize("field", ["shortfall_kwh", "expected_departure_percent"])
def test_oversized_json_integer_is_a_value_refusal_not_float_overflow(field):
    value = summary()
    detail = {
        "shortfall_kwh": 1.1,
        "expected_departure_percent": 20,
        "required_percent": 55,
        "drive_count": 1,
    }
    detail[field] = 10**1000
    value["vehicles"][0]["alerts"] = [{"kind": "insufficient_charge", "detail": detail}]
    wire = json.dumps(value, allow_nan=False)
    assert len(wire.encode()) < 128 * 1024
    with pytest.raises(ValueError):
        brief_ipc.project(json.loads(wire))


def _source_provider(tmp_path, monkeypatch):
    import sys
    from pathlib import Path

    owner = load_script("tessie-brief", "brief_ipc")
    original = Path(__file__).resolve().parents[1]
    root = tmp_path / "source"
    files = (
        ".tessl-plugin/plugin.json",
        "rules/vehicle-brief-policy.md",
        "skills/tessie-brief/references/host-contract.md",
        "skills/tessie-brief/SKILL.md",
        "skills/tessie-brief/scripts/tessie-brief.py",
        "skills/tessie-brief/scripts/brief_ipc.py",
        "skills/tessie-charge/scripts/charge_ipc.py",
        "skills/tessie-ops/scripts/tessie_native.py",
        "skills/tessie-ops/scripts/tessie_core.py",
    )
    for relative in files:
        file = root / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes((original / relative).read_bytes())
    monkeypatch.setattr(owner, "__file__", str(root / "skills/tessie-brief/scripts/brief_ipc.py"))
    monkeypatch.setattr(owner, "INSTALLED", tmp_path / "absent/scripts")
    monkeypatch.setattr(owner, "DEV", root / "skills/tessie-charge/scripts", raising=False)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.delitem(sys.modules, "tessie_core", raising=False)
    return owner, root


def _evil_same_size(raw, marker):
    import ast

    tree = ast.parse(raw)
    # Fixture payload: preserve the complete real module APIs, shorten only its
    # module docstring/comments, then append an observable inert import witness.
    if isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
        tree.body.pop(0)
    code = (
        ast.unparse(tree)
        + "\nfrom pathlib import Path\nPath("
        + repr(str(marker))
        + ").write_text('unverified code executed')\n"
    ).encode()
    assert len(code) < len(raw)
    return code + b" " * (len(raw) - len(code))


@pytest.mark.parametrize(
    "relative",
    [
        "skills/tessie-charge/scripts/charge_ipc.py",
        "skills/tessie-ops/scripts/tessie_native.py",
        "skills/tessie-ops/scripts/tessie_core.py",
    ],
)
def test_matching_timestamp_size_pyc_never_executes_in_complete_transport(
    tmp_path, monkeypatch, relative
):
    import os
    import py_compile

    owner, root = _source_provider(tmp_path, monkeypatch)
    target = root / relative
    original = target.read_bytes()
    meta = target.stat()
    marker = tmp_path / "cache-code-executed"
    target.write_bytes(_evil_same_size(original, marker))
    os.utime(target, ns=(meta.st_atime_ns, meta.st_mtime_ns))
    py_compile.compile(
        str(target), doraise=True, invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP
    )
    target.write_bytes(original)
    os.utime(target, ns=(meta.st_atime_ns, meta.st_mtime_ns))
    assert target.stat().st_size == meta.st_size
    assert target.stat().st_mtime_ns == meta.st_mtime_ns
    owner.native_type()  # Real charge -> native -> core composition, no IPC call.
    assert not marker.exists()


def test_swap_restore_during_real_path_code_load_never_executes_replacement(tmp_path, monkeypatch):
    import importlib.machinery
    import shutil

    owner, root = _source_provider(tmp_path, monkeypatch)
    target = root / "skills/tessie-charge/scripts/charge_ipc.py"
    marker = tmp_path / "swapped-code-executed"
    original_dir = target.parent
    replacement = tmp_path / "replacement"
    shutil.copytree(original_dir, replacement, ignore=shutil.ignore_patterns("__pycache__"))
    (replacement / target.name).write_bytes(_evil_same_size(target.read_bytes(), marker))
    retired = tmp_path / "held-original"
    get_code = importlib.machinery.SourceFileLoader.get_code
    attempts = []

    def swap(loader, fullname):
        if loader.path != str(target):
            return get_code(loader, fullname)
        attempts.append(fullname)
        original_dir.rename(retired)
        replacement.rename(original_dir)
        try:
            return get_code(loader, fullname)
        finally:
            original_dir.rename(replacement)
            retired.rename(original_dir)

    monkeypatch.setattr(importlib.machinery.SourceFileLoader, "get_code", swap)
    owner.native_type()
    assert not marker.exists()
    assert attempts == []  # The fixed byte factory never reopens provider code.


def test_real_private_factory_does_not_replace_global_provider_modules_or_imports(monkeypatch):
    import importlib.util
    import sys

    before = {
        name: sys.modules.get(name)
        for name in ("tessie_core", "tessie_charge_native", "tessie_brief_charge_transport")
    }
    path = list(sys.path)
    loader = importlib.util.spec_from_file_location
    brief_ipc.native_type()
    assert {name: sys.modules.get(name) for name in before} == before
    assert sys.path == path
    assert importlib.util.spec_from_file_location is loader


CAPTURE_PATHS = (
    ".tessl-plugin/plugin.json",
    "rules/vehicle-brief-policy.md",
    "skills/tessie-brief/references/host-contract.md",
    "skills/tessie-brief/SKILL.md",
    "skills/tessie-brief/scripts/tessie-brief.py",
    "skills/tessie-brief/scripts/brief_ipc.py",
    "skills/tessie-charge/scripts/charge_ipc.py",
    "skills/tessie-ops/scripts/tessie_native.py",
    "skills/tessie-ops/scripts/tessie_core.py",
)


def capture_hashes(provider):
    import hashlib

    return {
        relative: hashlib.sha256((provider / relative).read_bytes()).hexdigest()
        for relative in CAPTURE_PATHS
    }


@pytest.mark.parametrize("relative", CAPTURE_PATHS)
def test_initial_capture_mismatch_holds_before_any_transport_compile(
    tmp_path, monkeypatch, relative
):
    from pathlib import Path

    owner, provider, skills = _installed_provider(tmp_path, monkeypatch)
    expected = capture_hashes(provider)
    changed = provider / relative
    changed.write_bytes(changed.read_bytes() + b"\n")
    if relative in CAPTURE_PATHS[4:]:
        _, skill, *parts = Path(relative).parts
        (skills / ("tessl__" + skill) / Path(*parts)).write_bytes(changed.read_bytes())

    def forbidden(*args, **kwargs):
        raise AssertionError("An unexpected capture must hold before compiling transport")

    monkeypatch.setattr(owner.importlib.util, "module_from_spec", forbidden)
    with pytest.raises(ValueError):
        owner.call(expected_source_hashes=expected)


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "extra",
        "nonhex",
        "uppercase",
        "boolean",
        "list",
        "key-subclass",
        "value-subclass",
    ],
)
def test_expected_capture_requires_exact_known_inventory(tmp_path, monkeypatch, change):
    owner, provider, _ = _installed_provider(tmp_path, monkeypatch)
    expected = json.loads(json.dumps(capture_hashes(provider)))
    if change == "missing":
        expected.pop(CAPTURE_PATHS[0])
    if change == "extra":
        expected["caller/selected.py"] = "a" * 64
    if change == "nonhex":
        expected[CAPTURE_PATHS[0]] = "z" * 64
    if change == "uppercase":
        expected[CAPTURE_PATHS[0]] = "A" * 64
    if change == "boolean":
        expected[CAPTURE_PATHS[0]] = True
    if change in {"key-subclass", "value-subclass"}:

        class DerivedString(str):
            pass

        if change == "key-subclass":
            digest = expected.pop(CAPTURE_PATHS[0])
            expected[DerivedString(CAPTURE_PATHS[0])] = digest
        else:
            expected[CAPTURE_PATHS[0]] = DerivedString(expected[CAPTURE_PATHS[0]])
    if change == "list":
        expected = list(expected)
    with pytest.raises(ValueError):
        owner.call(expected_source_hashes=expected)


def test_expected_capture_is_owned_and_normal_call_remains_compatible(tmp_path, monkeypatch):
    owner, provider, _ = _installed_provider(tmp_path, monkeypatch)
    expected = capture_hashes(provider)
    bridge_type = owner.native_type(expected_source_hashes=expected)
    expected[CAPTURE_PATHS[0]] = "0" * 64
    bridge = bridge_type()
    assert bridge.call({"schema_version": 1, "operation": "summary"}, 200)["status"] == 200
    assert owner.call()["lines"] == []
    assert owner.call(expected_source_hashes=capture_hashes(provider))["lines"] == []


def test_matching_hashes_never_replace_provider_identity_admission(tmp_path, monkeypatch):
    owner, provider, _ = _installed_provider(tmp_path, monkeypatch)
    file = provider / ".tessl-plugin/plugin.json"
    value = json.loads(file.read_text())
    value["name"] = "jbaruch/impostor"
    file.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        owner.call(expected_source_hashes=capture_hashes(provider))
