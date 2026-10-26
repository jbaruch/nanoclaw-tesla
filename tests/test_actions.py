"""Cached reads, parameter validation, command outcomes and state confirmation."""

from __future__ import annotations

import json

import pytest

from support import (
    ADDRESS,
    LAT,
    LON,
    NOW,
    RUSTLER,
    FakeTransport,
    allowlist_document,
    json_response,
    standard_transport,
    state_payload,
)
from tessie_actions import (
    build_params,
    confirm_state,
    read_vehicle,
    resolve,
    run_command,
    run_drive_tag,
)
from tessie_core import TessieClient, TessieError
from tessie_policy import parse_allowlist


def vehicle_for(transport: FakeTransport):
    return resolve(TessieClient(transport), parse_allowlist(allowlist_document()), "The Rustler")


# --- reads ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["asleep", "waiting_for_sleep"])
def test_sleeping_vehicle_is_read_from_cache_and_never_woken(status: str) -> None:
    transport = standard_transport(status=status)
    vehicle = vehicle_for(transport)
    result = read_vehicle(TessieClient(transport), vehicle, "state", include_location=False)
    assert result["vehicle_status"] == status
    assert result["from_cache"] is True
    assert result["data"]["vehicle_state"]["locked"] is True
    # Only reads: no POST of any kind, no wake, no real-time (use_cache=false) read.
    assert transport.paths("POST") == []
    assert not any("wake" in path for path in transport.paths())
    assert all("use_cache" not in call["query"] for call in transport.calls)


def test_awake_vehicle_still_reads_the_cache() -> None:
    transport = standard_transport(status="awake")
    result = read_vehicle(
        TessieClient(transport), vehicle_for(transport), "battery", include_location=False
    )
    assert result["from_cache"] is False
    assert all("use_cache" not in call["query"] for call in transport.calls)


def test_status_read_stops_after_the_probe() -> None:
    transport = standard_transport()
    result = read_vehicle(
        TessieClient(transport), vehicle_for(transport), "status", include_location=False
    )
    assert "data" not in result
    assert transport.paths().count(f"/{RUSTLER}/state") == 0


def test_location_is_redacted_unless_explicitly_included() -> None:
    transport = standard_transport()
    client, vehicle = TessieClient(transport), vehicle_for(transport)
    hidden = json.dumps(read_vehicle(client, vehicle, "state", include_location=False))
    assert str(LAT) not in hidden and str(LON) not in hidden and ADDRESS not in hidden
    shown = json.dumps(read_vehicle(client, vehicle, "state", include_location=True))
    assert str(LAT) in shown and ADDRESS in shown


def test_malformed_status_payload_fails_visibly() -> None:
    transport = standard_transport()
    transport.routes[("GET", f"/{RUSTLER}/status")] = json_response({"nope": 1})
    with pytest.raises(TessieError) as caught:
        read_vehicle(
            TessieClient(transport), vehicle_for(transport), "state", include_location=False
        )
    assert caught.value.code == "malformed_response"


# --- parameter validation ------------------------------------------------------------


def test_parameters_are_validated_and_extras_rejected() -> None:
    assert build_params("lock", {"temperature": None}) == {}
    assert build_params("set_temperatures", {"temperature": 22}) == {"temperature": 22.0}
    assert build_params("set_charge_limit", {"percent": 80}) == {"percent": 80}
    assert build_params("share", {"value": " Somewhere "}) == {
        "value": "Somewhere",
        "locale": "en-US",
    }
    for op, raw in [
        ("set_temperatures", {"temperature": 14.9}),
        ("set_temperatures", {"temperature": 28.1}),
        ("set_temperatures", {}),
        ("set_charge_limit", {"percent": 49}),
        ("set_charge_limit", {"percent": 101}),
        ("set_charge_limit", {"percent": 80.5}),
        ("share", {"value": "bad\nvalue"}),
        ("share", {"value": "x", "locale": "english"}),
        ("lock", {"percent": 80}),
    ]:
        with pytest.raises(TessieError) as caught:
            build_params(op, raw)
        assert caught.value.code == "bad_parameter", (op, raw)


# --- command outcomes ----------------------------------------------------------------


def run(transport: FakeTransport, op: str, params=None, attempts: int = 3):
    return run_command(
        TessieClient(transport),
        vehicle_for(transport),
        op,
        params or {},
        max_attempts=attempts,
        now=lambda: NOW,
    )


def test_accepted_command_with_matching_fresh_state_is_confirmed() -> None:
    transport = standard_transport(state=state_payload(locked=True, stamp_s=NOW + 2))
    outcome = run(transport, "lock")
    assert outcome["tessie_result"] is True
    assert outcome["sent_at_epoch"] == NOW
    assert outcome["status"] == "confirmed"
    assert outcome["field"] == "vehicle_state.locked"
    assert outcome["observed"] is True


def test_accepted_command_with_stale_matching_state_is_unconfirmed() -> None:
    stale = NOW - 20
    outcome = run(standard_transport(state=state_payload(locked=True, stamp_s=stale)), "lock")
    assert (outcome["status"], outcome["reason"]) == ("unconfirmed", "stale_state")


@pytest.mark.parametrize(
    ("offset", "expected"),
    [(-10, "unconfirmed"), (-0.001, "unconfirmed"), (0, "confirmed"), (0.001, "confirmed")],
)
def test_confirmation_never_accepts_matching_pre_command_state(
    offset: float, expected: str
) -> None:
    outcome = run(
        standard_transport(state=state_payload(locked=True, stamp_s=NOW + offset)), "lock"
    )
    assert outcome["status"] == expected
    assert outcome["tessie_result"] is True
    if expected == "unconfirmed":
        assert outcome["reason"] == "stale_state"


@pytest.mark.parametrize("stamp", [True, float("nan"), float("inf"), float("-inf"), 1e300])
def test_invalid_provider_timestamps_preserve_an_unconfirmed_accepted_receipt(
    stamp: object,
) -> None:
    state = state_payload()
    state["vehicle_state"]["timestamp"] = stamp
    outcome = run(standard_transport(state=state), "lock")
    assert outcome["tessie_result"] is True
    assert (outcome["status"], outcome["reason"]) == ("unconfirmed", "no_timestamp")


def test_numeric_lock_value_is_not_boolean_confirmation() -> None:
    state = state_payload(stamp_s=NOW + 1)
    state["vehicle_state"]["locked"] = 1
    outcome = run(standard_transport(state=state), "lock")
    assert (outcome["status"], outcome["reason"]) == ("unconfirmed", "mismatch")


def test_accepted_command_with_mismatched_state_is_unconfirmed() -> None:
    outcome = run(standard_transport(state=state_payload(locked=False, stamp_s=NOW + 1)), "lock")
    assert (outcome["status"], outcome["reason"]) == ("unconfirmed", "mismatch")
    assert outcome["tessie_result"] is True


def test_result_false_is_failed_and_reads_nothing_back() -> None:
    transport = standard_transport(command_result=False)
    outcome = run(transport, "lock")
    assert outcome["status"] == "failed"
    assert transport.paths("GET").count(f"/{RUSTLER}/state") == 0


def test_actions_without_a_state_field_are_accepted_not_confirmed() -> None:
    for op, params in [("flash", {}), ("share", {"value": "Somewhere", "locale": "en-US"})]:
        outcome = run(standard_transport(), op, params)
        assert outcome["status"] == "accepted"
        assert outcome["reason"] == "no_state_field"


@pytest.mark.parametrize(
    ("op", "params", "state_kwargs", "expected"),
    [
        ("unlock", {}, {"locked": False}, "confirmed"),
        ("start_climate", {}, {"climate_on": True}, "confirmed"),
        ("stop_climate", {}, {"climate_on": False}, "confirmed"),
        ("stop_climate", {}, {"climate_on": True}, "unconfirmed"),
        ("set_temperatures", {"temperature": 21.0}, {"driver_temp": 21.0}, "confirmed"),
        ("set_temperatures", {"temperature": 23.0}, {"driver_temp": 21.0}, "unconfirmed"),
        ("start_charging", {}, {"charging_state": "Charging"}, "confirmed"),
        ("start_charging", {}, {"charging_state": "Disconnected"}, "unconfirmed"),
        ("stop_charging", {}, {"charging_state": "Stopped"}, "confirmed"),
        ("set_charge_limit", {"percent": 80}, {"charge_limit": 80}, "confirmed"),
        ("set_charge_limit", {"percent": 90}, {"charge_limit": 80}, "unconfirmed"),
    ],
)
def test_each_control_compares_its_own_state_field(op, params, state_kwargs, expected) -> None:
    transport = standard_transport(state=state_payload(stamp_s=NOW + 1, **state_kwargs))
    assert run(transport, op, params)["status"] == expected


def test_missing_state_field_or_timestamp_is_unconfirmed() -> None:
    transport = standard_transport(state={"vehicle_state": {"timestamp": int(NOW * 1000)}})
    assert run(transport, "lock")["reason"] == "field_missing"
    no_stamp = state_payload()
    del no_stamp["vehicle_state"]["timestamp"]
    assert run(standard_transport(state=no_stamp), "lock")["reason"] == "no_timestamp"


def test_a_failing_readback_is_a_visible_error_not_a_silent_confirm() -> None:
    transport = standard_transport()
    transport.routes[("GET", f"/{RUSTLER}/state")] = json_response({}, status=500)
    outcome = run(transport, "lock")
    assert outcome["tessie_result"] is True
    assert (outcome["status"], outcome["reason"]) == ("unconfirmed", "confirmation_unavailable")
    assert outcome["confirmation_error"] == {"code": "http_500", "http_status": 500}
    assert len(transport.paths("POST")) == 1


def test_command_sends_exactly_one_post_with_bounded_attempts() -> None:
    transport = standard_transport(state=state_payload(stamp_s=NOW + 1))
    run(transport, "lock", attempts=1)
    posts = [c for c in transport.calls if c["method"] == "POST"]
    assert len(posts) == 1
    assert posts[0]["query"]["max_attempts"] == "1"
    with pytest.raises(TessieError):
        run(transport, "lock", attempts=4)
    assert len([c for c in transport.calls if c["method"] == "POST"]) == 1


def test_confirm_state_alone_never_posts() -> None:
    transport = standard_transport(state=state_payload(stamp_s=NOW))
    result = confirm_state(
        TessieClient(transport), vehicle_for(transport), "lock", {}, since_epoch=NOW
    )
    assert result["status"] == "confirmed"
    assert transport.paths("POST") == []


def test_drive_tag_validates_ids_and_reports_acceptance_only() -> None:
    transport = standard_transport()
    client, vehicle = TessieClient(transport), vehicle_for(transport)
    ok = run_drive_tag(client, vehicle, drives="10001,10002", tag="Business")
    assert (ok["status"], ok["tessie_result"]) == ("accepted", True)
    with pytest.raises(TessieError):
        run_drive_tag(client, vehicle, drives="1; DROP", tag=None)
