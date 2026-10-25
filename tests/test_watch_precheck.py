"""tessie-watch precheck: stay silent when healthy, wake with evidence otherwise."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from support import ADDRESS, LAT, load_script

precheck = load_script("tessie-watch", "tessie-precheck")


def completed(stdout: str = "", stderr: str = "", code: int = 0):
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=stdout, stderr=stderr)


def state_reply(level, charging, status="asleep") -> str:
    return json.dumps(
        {
            "vehicle_status": status,
            "data": {"charge_state": {"battery_level": level, "charging_state": charging}},
        }
    )


class Scripted:
    """Answers each tessie-ops script by name and records the argv it was given."""

    def __init__(self, *, threshold=None, vehicles=("The Rustler", "Bradbury"), states=None):
        self.calls: list[list[str]] = []
        self.threshold = threshold
        self.vehicles = vehicles
        self.states = states or {}

    def __call__(self, argv):
        self.calls.append(list(argv))
        script = Path(argv[0]).name
        if script == "tessie-allowlist.py":
            return completed(json.dumps({"watch": {"low_battery_percent": self.threshold}}))
        if script == "tessie-vehicles.py":
            return completed(json.dumps({"vehicles": [{"alias": a} for a in self.vehicles]}))
        alias = argv[argv.index("--vehicle") + 1]
        return completed(self.states.get(alias, state_reply(64, "Disconnected")))


OPS = precheck.OPS_SCRIPTS_DEV


def test_healthy_vehicles_do_not_wake_the_agent() -> None:
    result = precheck.evaluate(Scripted(), OPS)
    assert result == {"wake_agent": False, "data": {"reason": "all_clear", "checked": 2}}


def test_low_unplugged_battery_wakes_with_the_evidence() -> None:
    runner = Scripted(states={"Bradbury": state_reply(12, "Disconnected")})
    result = precheck.evaluate(runner, OPS)
    assert result["wake_agent"] is True
    (alert,) = result["data"]["alerts"]
    assert alert["alias"] == "Bradbury"
    assert alert["kind"] == "low_battery_unplugged"
    assert (alert["battery_level"], alert["threshold"]) == (12, 20)


def test_low_battery_that_is_charging_stays_silent() -> None:
    runner = Scripted(states={"Bradbury": state_reply(12, "Charging")})
    assert precheck.evaluate(runner, OPS)["wake_agent"] is False


def test_threshold_comes_from_the_allowlist_watch_setting() -> None:
    runner = Scripted(threshold=70)
    assert precheck.evaluate(runner, OPS)["wake_agent"] is True  # 64% < 70% and unplugged
    assert precheck.evaluate(Scripted(threshold=60), OPS)["wake_agent"] is False


def test_incomplete_state_wakes_instead_of_passing_silently() -> None:
    runner = Scripted(states={"Bradbury": json.dumps({"vehicle_status": "asleep", "data": {}})})
    result = precheck.evaluate(runner, OPS)
    assert result["wake_agent"] is True
    assert result["data"]["alerts"][0]["kind"] == "state_incomplete"


def test_every_read_is_a_cached_state_read_and_never_a_wake() -> None:
    runner = Scripted()
    precheck.evaluate(runner, OPS)
    flat = [part for argv in runner.calls for part in argv]
    assert "wake" not in flat and "--include-location" not in flat
    reads = [a for a in runner.calls if Path(a[0]).name == "tessie-read.py"]
    assert [a[1] for a in reads] == ["state", "state"]


def test_a_failing_script_wakes_with_its_stderr_not_silence() -> None:
    def runner(argv):
        return completed(stderr="tessie: Tessie rejected the credential (HTTP 401)", code=1)

    result = precheck.evaluate(runner, OPS)
    assert result["wake_agent"] is True
    assert result["data"]["reason"] == "script_failed"
    assert "401" in result["data"]["error"]
    assert result["data"]["exit_code"] == 1


def test_timeouts_and_garbage_output_wake_with_a_reason() -> None:
    def timing_out(argv):
        raise subprocess.TimeoutExpired(argv, 1)

    assert precheck.evaluate(timing_out, OPS)["data"]["reason"] == "script_timeout"
    assert (
        precheck.evaluate(lambda argv: completed("not json"), OPS)["data"]["reason"] == "bad_output"
    )
    assert precheck.evaluate(lambda argv: completed("[1]"), OPS)["data"]["reason"] == "bad_output"


def test_missing_ops_scripts_fail_loudly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(precheck, "OPS_SCRIPTS_MOUNT", tmp_path / "absent")
    monkeypatch.setattr(precheck, "OPS_SCRIPTS_DEV", tmp_path / "also-absent")
    result = precheck.evaluate(Scripted())
    assert result["wake_agent"] is True
    assert "reinstall" in result["data"]["error"]


def test_dev_fallback_resolves_the_sibling_skill_when_the_mount_is_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(precheck, "OPS_SCRIPTS_MOUNT", tmp_path / "absent")
    assert precheck.ops_scripts_dir() == precheck.OPS_SCRIPTS_DEV


def test_wake_payloads_carry_no_coordinates() -> None:
    runner = Scripted(states={"Bradbury": state_reply(12, "Disconnected")})
    blob = json.dumps(precheck.evaluate(runner, OPS))
    assert str(LAT) not in blob and ADDRESS not in blob


def test_main_prints_the_contract_as_the_last_stdout_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(precheck, "evaluate", lambda: {"wake_agent": False, "data": {}})
    assert precheck.main() == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1]) == {"wake_agent": False, "data": {}}


def test_unexpected_errors_fail_open_with_a_wake(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom():
        raise RuntimeError("bug")

    monkeypatch.setattr(precheck, "evaluate", boom)
    assert precheck.main() == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out.splitlines()[-1])
    assert payload["wake_agent"] is True
    assert payload["data"]["reason"] == "precheck_error"
    assert "RuntimeError" in payload["data"]["error"]
    assert "bug" in captured.err
