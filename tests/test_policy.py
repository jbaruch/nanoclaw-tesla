"""Allowlist, selection and host-witnessed chat authorization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from support import (
    BLUE_ROCKET,
    BRADBURY,
    CONTROL_CHAT,
    OWNER_CHAT,
    POWERSLAVE,
    READ_CHAT,
    RUSTLER,
    STRANGER_CHAT,
    UNNAMED,
    allowlist_document,
    inventory_payload,
    write_allowlist,
    write_environ,
)
from tessie_core import EXIT_DENIED, TessieError
from tessie_policy import (
    ROLE_CONTROL,
    ROLE_OWNER,
    ROLE_READ,
    authorize,
    denied_summary,
    load_allowlist,
    parse_allowlist,
    parse_inventory,
    role_for,
    select_vehicle,
    witnessed_chat_jid,
)


def allowlist(**overrides):
    return parse_allowlist(allowlist_document(**overrides))


def inventory():
    return parse_inventory(inventory_payload())


# --- allowlist file ------------------------------------------------------------------


def test_missing_allowlist_is_default_deny(tmp_path: Path) -> None:
    with pytest.raises(TessieError) as caught:
        load_allowlist(tmp_path / "absent.json")
    assert caught.value.code == "allowlist_missing"
    assert caught.value.exit_code == EXIT_DENIED
    assert "docs/setup.md" in caught.value.message


def test_symlinked_allowlist_is_refused(tmp_path: Path) -> None:
    real = write_allowlist(tmp_path / "real.json")
    link = tmp_path / "link.json"
    link.symlink_to(real)
    with pytest.raises(TessieError) as caught:
        load_allowlist(link)
    assert caught.value.code == "allowlist_invalid"


def test_malformed_json_and_unknown_schema_are_refused(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(TessieError) as caught:
        load_allowlist(bad)
    assert caught.value.code == "allowlist_invalid"
    with pytest.raises(TessieError) as schema:
        parse_allowlist(allowlist_document(schema_version=2))
    assert schema.value.code == "allowlist_schema"


@pytest.mark.parametrize(
    "overrides",
    [
        {"vehicles": [{"vin": "short", "alias": "x"}]},
        {"vehicles": [{"vin": RUSTLER, "alias": ""}]},
        {"vehicles": [{"vin": RUSTLER, "alias": "A", "shared": "yes"}]},
        {"vehicles": [{"vin": RUSTLER, "alias": "A"}, {"vin": BRADBURY, "alias": "a"}]},
        {"vehicles": [{"vin": RUSTLER, "alias": "A"}, {"vin": RUSTLER, "alias": "B"}]},
        {"default_vehicle": "Nobody"},
        {"owner_chats": "tg:x"},
        {"watch": {"low_battery_percent": 0}},
    ],
)
def test_invalid_allowlists_fail_closed(overrides) -> None:
    with pytest.raises(TessieError) as caught:
        parse_allowlist(allowlist_document(**overrides))
    assert caught.value.exit_code == EXIT_DENIED


# --- selection -----------------------------------------------------------------------


def test_owner_active_listed_vehicle_resolves_by_alias_vin_and_case() -> None:
    for selector in ("The Rustler", "the  rustler", RUSTLER, RUSTLER.lower()):
        vehicle = select_vehicle(selector, allowlist(), inventory())
        assert (vehicle.alias, vehicle.vin_suffix) == ("The Rustler", "1832")


def test_driver_null_access_and_inactive_listed_vehicles_are_denied() -> None:
    cases = {
        POWERSLAVE: "not_owner_access",
        UNNAMED: "not_owner_access",
        BLUE_ROCKET: "not_owner_access",
    }
    for vin, reason in cases.items():
        doc = allowlist(vehicles=[{"vin": vin, "alias": "Listed"}], default_vehicle=None)
        with pytest.raises(TessieError) as caught:
            select_vehicle("Listed", doc, inventory())
        assert caught.value.code == reason


def test_owner_vehicle_that_went_inactive_is_denied() -> None:
    payload = inventory_payload()
    payload["results"][0]["is_active"] = False
    with pytest.raises(TessieError) as caught:
        select_vehicle("The Rustler", allowlist(), parse_inventory(payload))
    assert caught.value.code == "inactive"


@pytest.mark.parametrize(
    "row",
    [
        None,
        42,
        {},
        {"vin": 7},
        {"vin": "invalid"},
        {"vin": RUSTLER, "last_state": []},
        {"vin": RUSTLER, "is_active": "true"},
    ],
)
def test_malformed_inventory_rows_refuse_the_whole_response(row):
    good = inventory_payload()["results"][1]
    with pytest.raises(TessieError) as caught:
        parse_inventory({"results": [good, row]})
    assert caught.value.code == "malformed_response"
    assert "report" in caught.value.message


def test_duplicate_inventory_rows_are_not_last_writer_wins():
    row = inventory_payload()["results"][0]
    with pytest.raises(TessieError) as caught:
        parse_inventory({"results": [row, row]})
    assert caught.value.code == "malformed_response"


def test_unlisted_vin_and_unknown_alias_are_denied() -> None:
    with pytest.raises(TessieError) as vin:
        select_vehicle(POWERSLAVE, allowlist(), inventory())
    assert vin.value.code == "not_allowlisted"
    with pytest.raises(TessieError) as alias:
        select_vehicle("Powerslave", allowlist(), inventory())
    assert alias.value.code == "unknown_alias"
    assert "Powerslave" in alias.value.message  # echoes the request
    assert POWERSLAVE not in alias.value.message


def test_shared_flag_overrides_access_checks_only_for_listed_vehicles() -> None:
    doc = allowlist(
        vehicles=[{"vin": POWERSLAVE, "alias": "Powerslave", "shared": True}],
        default_vehicle=None,
    )
    assert select_vehicle("Powerslave", doc, inventory()).vin_suffix == "7263"
    with pytest.raises(TessieError) as caught:  # still not listed: BLUE_ROCKET
        select_vehicle(BLUE_ROCKET, doc, inventory())
    assert caught.value.code == "not_allowlisted"


def test_listed_vehicle_missing_from_live_inventory_is_denied() -> None:
    payload = inventory_payload()
    payload["results"] = payload["results"][1:]
    with pytest.raises(TessieError) as caught:
        select_vehicle("The Rustler", allowlist(), parse_inventory(payload))
    assert caught.value.code == "not_in_live_inventory"


def test_default_vehicle_then_single_candidate_then_explicit_selector_required() -> None:
    assert select_vehicle(None, allowlist(), inventory()).alias == "The Rustler"
    two = allowlist(default_vehicle=None)
    with pytest.raises(TessieError) as caught:
        select_vehicle(None, two, inventory())
    assert caught.value.code == "selector_required"
    assert "Bradbury" in caught.value.message and "The Rustler" in caught.value.message
    one = allowlist(default_vehicle=None, vehicles=[{"vin": BRADBURY, "alias": "Bradbury"}])
    assert select_vehicle(None, one, inventory()).alias == "Bradbury"


def test_denied_summary_lists_everything_not_addressable_without_coordinates() -> None:
    rows = denied_summary(allowlist(), inventory())
    labels = {r["alias_or_suffix"]: r for r in rows}
    assert set(labels) == {"Powerslave", "Blue Rocket", f"…{UNNAMED[-4:]}"}
    assert labels["Powerslave"]["denied_reason"] == "not_allowlisted"
    assert labels["Powerslave"]["access_type"] == "DRIVER"
    blob = json.dumps(rows)
    assert "latitude" not in blob and POWERSLAVE not in blob and "41.12" not in blob


# --- witnessed chat authorization ----------------------------------------------------


def test_roles_come_from_the_allowlist_only() -> None:
    doc = allowlist()
    assert role_for(OWNER_CHAT, doc) == ROLE_OWNER
    assert role_for(CONTROL_CHAT, doc) == ROLE_CONTROL
    assert role_for(READ_CHAT, doc) == ROLE_READ
    assert role_for(STRANGER_CHAT, doc) is None


def test_witness_reads_the_host_value_from_the_init_environment(tmp_path: Path) -> None:
    environ = write_environ(tmp_path / "environ", OWNER_CHAT)
    assert witnessed_chat_jid(environ_path=environ, env={}) == OWNER_CHAT
    assert (
        witnessed_chat_jid(environ_path=environ, env={"NANOCLAW_CHAT_JID": OWNER_CHAT})
        == OWNER_CHAT
    )


def test_a_command_line_override_of_the_chat_id_is_refused(tmp_path: Path) -> None:
    environ = write_environ(tmp_path / "environ", STRANGER_CHAT)
    with pytest.raises(TessieError) as caught:
        witnessed_chat_jid(environ_path=environ, env={"NANOCLAW_CHAT_JID": OWNER_CHAT})
    assert caught.value.code == "chat_identity_mismatch"
    assert caught.value.exit_code == EXIT_DENIED


def test_unwitnessable_chat_denies(tmp_path: Path) -> None:
    with pytest.raises(TessieError) as unreadable:
        witnessed_chat_jid(environ_path=tmp_path / "absent", env={})
    assert unreadable.value.code == "chat_unwitnessed"
    environ = write_environ(tmp_path / "environ", None)
    with pytest.raises(TessieError) as missing:
        witnessed_chat_jid(environ_path=environ, env={"NANOCLAW_CHAT_JID": OWNER_CHAT})
    assert missing.value.code == "chat_unwitnessed"


@pytest.mark.parametrize(
    ("chat", "minimum", "allowed"),
    [
        (OWNER_CHAT, ROLE_OWNER, True),
        (CONTROL_CHAT, ROLE_OWNER, False),
        (CONTROL_CHAT, ROLE_CONTROL, True),
        (READ_CHAT, ROLE_CONTROL, False),
        (READ_CHAT, ROLE_READ, True),
        (STRANGER_CHAT, ROLE_READ, False),
    ],
)
def test_authorize_enforces_the_role_ladder(tmp_path: Path, chat, minimum, allowed) -> None:
    environ = write_environ(tmp_path / "environ", chat)
    if allowed:
        assert authorize(allowlist(), minimum, "test", environ_path=environ, env={})
    else:
        with pytest.raises(TessieError) as caught:
            authorize(allowlist(), minimum, "test", environ_path=environ, env={})
        assert caught.value.exit_code == EXIT_DENIED
