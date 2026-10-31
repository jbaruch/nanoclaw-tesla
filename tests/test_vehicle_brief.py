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
