"""End-to-end through the shipped CLI scripts with a fake transport."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from support import (
    ADDRESS,
    CONTROL_CHAT,
    LAT,
    NOW,
    OWNER_CHAT,
    POWERSLAVE,
    READ_CHAT,
    RUSTLER,
    STRANGER_CHAT,
    allowlist_document,
    json_response,
    load_script,
    make_runtime,
    standard_transport,
    state_payload,
)

vehicles = load_script("tessie-ops", "tessie-vehicles")
allowlist_cli = load_script("tessie-ops", "tessie-allowlist")
reader = load_script("tessie-ops", "tessie-read")
command = load_script("tessie-ops", "tessie-command")
confirm = load_script("tessie-ops", "tessie-confirm")


def run(module, argv, tmp_path: Path, transport=None, **kwargs):
    transport = transport or standard_transport()
    runtime, out, err = make_runtime(tmp_path, transport, **kwargs)
    code = module.main(argv, runtime=runtime)
    return code, out.getvalue(), err.getvalue(), transport


def parse(text: str) -> dict:
    return json.loads(text)


# --- tessie-vehicles -----------------------------------------------------------------


def test_vehicles_lists_only_addressable_cars_without_coordinates(tmp_path: Path) -> None:
    code, out, _, _ = run(vehicles, [], tmp_path, chat=READ_CHAT)
    payload = parse(out)
    assert code == 0
    assert [v["alias"] for v in payload["vehicles"]] == ["The Rustler", "Bradbury"]
    assert "denied" not in payload
    assert str(LAT) not in out and RUSTLER not in out


def test_denied_listing_is_owner_only(tmp_path: Path) -> None:
    code, out, _, _ = run(vehicles, ["--include-denied"], tmp_path, chat=OWNER_CHAT)
    denied = parse(out)["denied"]
    assert code == 0
    assert {r["alias_or_suffix"] for r in denied} >= {"Powerslave", "Blue Rocket"}
    assert POWERSLAVE not in out and str(LAT) not in out
    code, out, err, _ = run(vehicles, ["--include-denied"], tmp_path, chat=CONTROL_CHAT)
    assert (code, out) == (4, "")
    assert "owner" in err


def test_unknown_chat_gets_nothing(tmp_path: Path) -> None:
    transport = standard_transport()
    code, out, err, transport = run(vehicles, [], tmp_path, transport, chat=STRANGER_CHAT)
    assert (code, out) == (4, "")
    assert "not authorized" in err
    assert transport.calls == []  # denied before any request


# --- tessie-allowlist ----------------------------------------------------------------


def test_allowlist_show_hides_chat_ids_and_full_vins(tmp_path: Path) -> None:
    code, out, _, transport = run(allowlist_cli, ["show"], tmp_path, chat=READ_CHAT)
    assert code == 0
    assert OWNER_CHAT not in out and RUSTLER not in out
    assert parse(out)["vehicles"][0] == {
        "alias": "The Rustler",
        "vin_suffix": "1832",
        "shared": False,
    }
    assert transport.calls == []


def test_allowlist_resolve_denies_a_driver_car_with_a_reason(tmp_path: Path) -> None:
    doc = allowlist_document(
        vehicles=[{"vin": POWERSLAVE, "alias": "Powerslave"}], default_vehicle=None
    )
    code, out, err, _ = run(
        allowlist_cli, ["resolve", "--vehicle", "Powerslave"], tmp_path, document=doc
    )
    assert (code, out) == (4, "")
    assert "not_owner_access" in err


# --- tessie-read ---------------------------------------------------------------------


def test_read_state_from_a_sleeping_car_uses_cache_and_redacts(tmp_path: Path) -> None:
    transport = standard_transport(status="asleep")
    code, out, _, transport = run(reader, ["state"], tmp_path, transport, chat=READ_CHAT)
    payload = parse(out)
    assert code == 0
    assert payload["vehicle_status"] == "asleep" and payload["from_cache"] is True
    assert str(LAT) not in out and ADDRESS not in out
    assert transport.paths("POST") == []


def test_include_location_needs_an_owner_chat(tmp_path: Path) -> None:
    code, out, err, transport = run(
        reader, ["state", "--include-location"], tmp_path, chat=CONTROL_CHAT
    )
    assert (code, out) == (4, "")
    assert "owner" in err
    assert transport.calls == []
    code, out, _, _ = run(reader, ["state", "--include-location"], tmp_path, chat=OWNER_CHAT)
    assert code == 0 and str(LAT) in out


def test_location_read_requires_the_flag_and_an_owner_chat(tmp_path: Path) -> None:
    code, out, err, _ = run(reader, ["location"], tmp_path, chat=OWNER_CHAT)
    assert (code, out) == (4, "") and "--include-location" in err
    code, out, err, _ = run(reader, ["location", "--include-location"], tmp_path, chat=CONTROL_CHAT)
    assert (code, out) == (4, "")
    code, out, _, _ = run(reader, ["location", "--include-location"], tmp_path, chat=OWNER_CHAT)
    assert code == 0 and ADDRESS in out


def test_a_claimed_owner_chat_in_the_command_environment_cannot_grant_location(
    tmp_path: Path,
) -> None:
    code, out, err, transport = run(
        reader,
        ["location", "--include-location"],
        tmp_path,
        chat=STRANGER_CHAT,
        env={"NANOCLAW_CHAT_JID": OWNER_CHAT},
    )
    assert (code, out) == (4, "")
    assert "disagrees" in err
    assert transport.calls == []


def test_drivers_read_is_owner_only(tmp_path: Path) -> None:
    code, _, _, _ = run(reader, ["drivers"], tmp_path, chat=CONTROL_CHAT)
    assert code == 4
    code, out, _, _ = run(reader, ["drivers"], tmp_path, chat=OWNER_CHAT)
    assert code == 0 and "Synthetic Driver" in out


def test_drive_filters_apply_to_drives_and_coordinates_are_stripped(tmp_path: Path) -> None:
    code, out, _, transport = run(
        reader,
        ["drives", "--from", "1", "--to", "2", "--tag", "Business"],
        tmp_path,
        chat=READ_CHAT,
    )
    assert code == 0
    drives_call = next(c for c in transport.calls if c["path"].endswith("/drives"))
    assert drives_call["query"] == {"from": "1", "to": "2", "tag": "Business"}
    assert ADDRESS not in out and "starting_saved_location" in out


def test_drive_filters_on_other_reads_are_a_usage_error(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as caught:
        run(reader, ["state", "--tag", "x"], tmp_path)
    assert caught.value.code == 2


def test_http_failure_prints_a_diagnostic_and_no_stdout(tmp_path: Path) -> None:
    transport = standard_transport()
    transport.routes[("GET", f"/{RUSTLER}/status")] = json_response({}, status=401)
    code, out, err, _ = run(reader, ["state"], tmp_path, transport)
    assert (code, out) == (1, "")
    assert "401" in err and "dash.tessie.com/settings/api" in err


# --- tessie-command ------------------------------------------------------------------


def test_dry_run_prints_the_plan_and_sends_no_post(tmp_path: Path) -> None:
    code, out, _, transport = run(command, ["lock", "--dry-run"], tmp_path, chat=CONTROL_CHAT)
    payload = parse(out)
    assert code == 0 and payload["status"] == "planned"
    assert payload["confirm_with"] == "The Rustler:lock"
    assert payload["vehicle"] == {"alias": "The Rustler", "vin_suffix": "1832"}
    assert transport.paths("POST") == []


def test_command_without_the_echoed_confirmation_is_refused(tmp_path: Path) -> None:
    code, out, err, transport = run(command, ["lock"], tmp_path, chat=CONTROL_CHAT)
    assert (code, out) == (4, "")
    assert '--confirm "The Rustler:lock"' in err
    assert transport.paths("POST") == []
    code, out, _, transport = run(
        command, ["lock", "--confirm", "Bradbury:lock"], tmp_path, chat=CONTROL_CHAT
    )
    assert code == 4 and transport.paths("POST") == []


def test_read_chats_cannot_control_a_vehicle(tmp_path: Path) -> None:
    code, out, err, transport = run(
        command, ["lock", "--confirm", "The Rustler:lock"], tmp_path, chat=READ_CHAT
    )
    assert (code, out) == (4, "")
    assert transport.calls == []


def test_confirmed_lock_end_to_end(tmp_path: Path) -> None:
    transport = standard_transport(state=state_payload(locked=True, stamp_s=NOW + 1))
    code, out, _, transport = run(
        command,
        ["lock", "--confirm", "the rustler:LOCK", "--max-attempts", "1"],
        tmp_path,
        transport,
        chat=CONTROL_CHAT,
    )
    payload = parse(out)
    assert code == 0
    assert (payload["status"], payload["tessie_result"]) == ("confirmed", True)
    assert payload["max_attempts"] == 1
    assert RUSTLER not in out
    post = next(c for c in transport.calls if c["method"] == "POST")
    assert post["path"] == f"/{RUSTLER}/command/lock"
    assert post["query"]["wait_for_completion"] == "true"


def test_unconfirmed_control_exits_nonzero_with_json_and_a_warning(tmp_path: Path) -> None:
    transport = standard_transport(state=state_payload(locked=False, stamp_s=NOW + 1))
    code, out, err, _ = run(
        command, ["lock", "--confirm", "The Rustler:lock"], tmp_path, transport, chat=OWNER_CHAT
    )
    assert code == 3
    assert parse(out)["status"] == "unconfirmed"
    assert "do not report it as done" in err


def test_result_false_exits_one(tmp_path: Path) -> None:
    transport = standard_transport(command_result=False)
    code, out, err, _ = run(
        command, ["lock", "--confirm", "The Rustler:lock"], tmp_path, transport, chat=OWNER_CHAT
    )
    assert code == 1 and parse(out)["status"] == "failed"
    assert "result false" in err


def test_parameter_errors_are_caught_before_any_request(tmp_path: Path) -> None:
    code, out, err, transport = run(
        command,
        ["set_charge_limit", "--percent", "20", "--confirm", "The Rustler:set_charge_limit"],
        tmp_path,
        chat=OWNER_CHAT,
    )
    assert (code, out) == (1, "") and "50..100" in err
    assert transport.calls == []


def test_unsupported_actions_are_rejected_by_argparse(tmp_path: Path) -> None:
    for action in ("wake", "honk", "remote_start", "open_charge_port"):
        with pytest.raises(SystemExit) as caught:
            run(command, [action], tmp_path)
        assert caught.value.code == 2


def test_drive_tag_goes_through_the_same_confirmation(tmp_path: Path) -> None:
    code, _, _, transport = run(
        command, ["set_drive_tag", "--drives", "10001"], tmp_path, chat=CONTROL_CHAT
    )
    assert code == 4 and transport.paths("POST") == []
    code, out, _, _ = run(
        command,
        [
            "set_drive_tag",
            "--drives",
            "10001",
            "--tag",
            "Business",
            "--confirm",
            "The Rustler:set_drive_tag",
        ],
        tmp_path,
        chat=CONTROL_CHAT,
    )
    assert code == 0 and parse(out)["status"] == "accepted"


# --- tessie-confirm ------------------------------------------------------------------


def test_confirm_reports_stale_state_as_unconfirmed(tmp_path: Path) -> None:
    transport = standard_transport(state=state_payload(locked=True, stamp_s=NOW - 600))
    code, out, _, transport = run(
        confirm, ["lock", "--since", str(NOW)], tmp_path, transport, chat=READ_CHAT
    )
    assert code == 3 and parse(out)["reason"] == "stale_state"
    assert transport.paths("POST") == []


def test_confirm_requires_since(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as caught:
        run(confirm, ["lock"], tmp_path)
    assert caught.value.code == 2
