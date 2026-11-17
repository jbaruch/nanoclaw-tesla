"""Replay documented Tessie/TripIt shapes; Navan rows are explicit extractions.

Shape evidence: https://developer.tessie.com/reference/get-drives (results,
started_at/ended_at, odometer_distance, tag) and
https://tripit.github.io/api/doc/v1/ (AirObject/Segment/StartDateTime).
Fixtures are synthetic; no live account, booking, vehicle or provider writes.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime

import pytest

from support import (
    BRADBURY,
    READ_CHAT,
    RUSTLER,
    FakeTransport,
    inventory_payload,
    json_response,
    load_script,
    make_runtime,
)

mileage = load_script("tessie-ops", "tessie-mileage")


def epoch(value):
    return int(datetime.fromisoformat(value).timestamp())


def segment(date, time, origin, destination, number, arrival_date, arrival_time, offset):
    return {
        "StartDateTime": {"date": date, "time": time, "utc_offset": offset},
        "EndDateTime": {"date": arrival_date, "time": arrival_time, "utc_offset": offset},
        "start_airport_code": origin,
        "end_airport_code": destination,
        "marketing_airline_code": "DL",
        "marketing_flight_number": number,
    }


def sources():
    return {
        "month": "2025-11",
        "timezone": "America/Chicago",
        "airport_locations": {"Nashville International Airport": "BNA"},
        "bookings": [
            {
                "source": "port-mail-ingress",
                "account": "baruchs@port.io",
                "purpose": 'Work, "Conference"',
                "flights": [
                    {
                        "date": "2025-11-01",
                        "from": "BNA",
                        "to": "SEA",
                        "airline": "DL",
                        "number": "123",
                    }
                ],
            }
        ],
        "tripit": {
            "AirObject": [
                {
                    "id": "1413",
                    "trip_id": "426",
                    "Segment": [
                        segment(
                            "2025-11-01",
                            "10:00:00",
                            "BNA",
                            "SEA",
                            "123",
                            "2025-11-01",
                            "14:00:00",
                            "-05:00",
                        ),
                        segment(
                            "2025-11-05",
                            "14:00:00",
                            "SEA",
                            "BNA",
                            "321",
                            "2025-11-05",
                            "18:00:00",
                            "-06:00",
                        ),
                    ],
                }
            ]
        },
    }


def drive(drive_id, begin, end, origin, destination, miles=12.345, tag=None):
    # odometer_distance is the documented API field, not the old distance stub.
    return {
        "id": drive_id,
        "started_at": epoch(begin),
        "ended_at": epoch(end),
        "starting_location": origin,
        "ending_location": destination,
        "starting_latitude": 36.1,
        "starting_longitude": -86.7,
        "ending_latitude": 36.2,
        "ending_longitude": -86.8,
        "odometer_distance": miles,
        "tag": tag,
    }


def round_trip():
    return [
        drive(
            10001,
            "2025-11-01T08:00:00-05:00",
            "2025-11-01T08:30:00-05:00",
            "Home, Nashville",
            "Nashville International Airport",
        ),
        drive(
            10002,
            "2025-11-05T19:00:00-06:00",
            "2025-11-05T19:30:00-06:00",
            "Nashville International Airport",
            "Home, Nashville",
            10.25,
        ),
    ]


def execute(tmp_path, data, drives, *, second=None, chat=None, include_location=True):
    transport = FakeTransport({("GET", "/vehicles"): json_response(inventory_payload())})
    for vin, rows in ((RUSTLER, drives), (BRADBURY, second or [])):
        transport.routes[("GET", f"/{vin}/status")] = json_response({"status": "asleep"})

        def queried_drives(rows=rows):
            query = transport.calls[-1]["query"]
            return json_response(
                {
                    "results": [
                        row
                        for row in rows
                        if int(query["from"]) <= row["started_at"] < int(query["to"])
                    ]
                }
            )

        transport.routes[("GET", f"/{vin}/drives")] = queried_drives
    kwargs = {"chat": chat} if chat else {}
    rt, out, err = make_runtime(tmp_path, transport, **kwargs)
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data))
    args = [str(path)] + (["--include-location"] if include_location else [])
    code = mileage.main(args, runtime=rt)
    return code, json.loads(out.getvalue()) if out.getvalue() else None, err.getvalue(), transport


def test_both_airport_legs_csv_and_cached_reads(tmp_path):
    rows = round_trip()
    code, result, err, transport = execute(tmp_path, sources(), rows + [rows[0]])
    assert code == 0 and not err and result is not None
    assert [row["drive_id"] for row in result["business"]] == [10001, 10002]
    assert result["ambiguous"] == []
    assert list(csv.reader(io.StringIO(result["csv"]))) == [
        ["date", "from", "to", "miles", "purpose", "vehicle"],
        [
            "2025-11-01",
            "Home, Nashville",
            "Nashville International Airport",
            "12.35",
            'Work, "Conference"',
            "The Rustler",
        ],
        [
            "2025-11-05",
            "Nashville International Airport",
            "Home, Nashville",
            "10.25",
            'Work, "Conference"',
            "The Rustler",
        ],
    ]
    assert result["summary"] == (
        "2025-11: 2 work drives, 22.60 miles; 0 drives need confirmation; "
        "Tessie tags not applied by this report."
    )
    assert all(call["method"] == "GET" for call in transport.calls)
    query = next(c["query"] for c in transport.calls if c["path"].endswith("/drives"))
    assert query == {
        "from": str(epoch("2025-10-31T18:00:00-05:00")),
        "to": str(epoch("2025-12-01T06:00:00-06:00")),
    }


def test_personal_and_uncertain_drives_wait_for_one_batch(tmp_path):
    rows = round_trip()
    rows[0]["tag"] = "Personal"
    rows[1]["starting_location"] = "Unresolved airport address"
    within = drive(
        10003, "2025-11-03T09:00:00-06:00", "2025-11-03T09:30:00-06:00", "Hotel", "Conference"
    )
    code, result, _, transport = execute(tmp_path, sources(), rows, second=[within])
    assert code == 0 and result is not None
    assert result["business"] == []
    assert [r["drive_id"] for r in result["ambiguous"]] == [10001, 10003, 10002]
    assert "existing tag" in result["ambiguous"][0]["reason"]
    assert len(list(csv.reader(io.StringIO(result["csv"])))) == 1
    assert all(call["method"] == "GET" for call in transport.calls)


def test_explicit_batch_decision_includes_personal_row_without_writing_tag(tmp_path):
    data = sources()
    rows = round_trip()
    rows[0]["tag"] = "Personal"
    data["confirmed"] = [
        {"vin_suffix": RUSTLER[-4:], "drive_id": 10001, "purpose": "Owner confirmed work trip"}
    ]
    code, result, _, transport = execute(tmp_path, data, rows)
    assert code == 0 and result is not None and result["ambiguous"] == []
    assert result["business"][0]["purpose"] == "Owner confirmed work trip"
    assert len(result["business"]) == 2
    assert all(c["method"] == "GET" for c in transport.calls)


def test_competing_airport_drives_across_vehicles_are_ambiguous(tmp_path):
    rows = round_trip()
    code, result, _, _ = execute(tmp_path, sources(), rows, second=[dict(rows[0], id=20001)])
    assert code == 0 and result is not None
    assert [r["drive_id"] for r in result["business"]] == [10002]
    assert len(result["ambiguous"]) == 2
    assert all("multiple drives" in r["reason"] for r in result["ambiguous"])


@pytest.mark.parametrize("month,expected", [("2025-10", 10001), ("2025-11", 10002)])
@pytest.mark.parametrize("leg", ["departure", "return"])
def test_competing_airport_drives_across_months_need_confirmation(tmp_path, month, expected, leg):
    data = sources()
    data["month"] = month
    segments = data["tripit"]["AirObject"][0]["Segment"]
    if leg == "departure":
        segments[0]["StartDateTime"]["time"] = "02:00:00"
        times = [
            ("2025-10-31T22:00:00-05:00", "2025-10-31T22:30:00-05:00"),
            ("2025-11-01T00:00:00-05:00", "2025-11-01T00:30:00-05:00"),
        ]
        origin, destination = "Home", "Nashville International Airport"
    else:
        data["bookings"][0]["flights"][0]["date"] = "2025-10-29"
        for field in ("StartDateTime", "EndDateTime"):
            segments[0][field]["date"] = "2025-10-29"
            segments[1][field]["date"] = "2025-10-31"
        segments[1]["EndDateTime"]["time"] = "23:00:00"
        segments[1]["EndDateTime"]["utc_offset"] = "-05:00"
        times = [
            ("2025-10-31T23:15:00-05:00", "2025-10-31T23:45:00-05:00"),
            ("2025-11-01T00:30:00-05:00", "2025-11-01T01:00:00-05:00"),
        ]
        origin, destination = "Nashville International Airport", "Home"
    rows = [
        drive(10001 + i, begin, end, origin, destination) for i, (begin, end) in enumerate(times)
    ]
    code, result, err, transport = execute(tmp_path, data, rows[:1], second=rows[1:])
    assert code == 0 and not err and result is not None
    assert result["business"] == []
    assert [r["drive_id"] for r in result["ambiguous"]] == [expected]
    assert "multiple drives" in result["ambiguous"][0]["reason"]
    assert len(list(csv.reader(io.StringIO(result["csv"])))) == 1
    for call in transport.calls:
        if call["path"].endswith("/drives"):
            assert int(call["query"]["from"]) <= rows[0]["started_at"]
            assert int(call["query"]["to"]) > rows[1]["started_at"]


@pytest.mark.parametrize("with_air", [False, True])
def test_tripit_error_fails_without_partial_csv_or_vehicle_reads(tmp_path, with_air):
    data = sources()
    if not with_air:
        data["tripit"] = {}
    data["tripit"]["Error"] = {"code": "500", "description": "Unavailable"}
    code, result, err, transport = execute(tmp_path, data, round_trip())
    assert code == 1 and result is None
    assert "refresh complete TripIt/Tessie/calendar source data" in err
    assert transport.calls == []


def event_sources():
    data = sources()
    data["bookings"] = []
    data["tripit"] = {"AirObject": []}
    data["work_events"] = [
        {
            "id": "work-event-1",
            "summary": 'Work, "Meetup"',
            "location": "Conference Hall",
            "start": {"dateTime": "2025-11-10T10:00:00-06:00"},
            "end": {"dateTime": "2025-11-10T17:00:00-06:00"},
        }
    ]
    return data


def event_drives():
    return [
        drive(
            10011,
            "2025-11-10T09:00:00-06:00",
            "2025-11-10T09:30:00-06:00",
            "Home",
            "Conference Hall",
        ),
        drive(
            10012,
            "2025-11-10T17:30:00-06:00",
            "2025-11-10T18:00:00-06:00",
            "Conference Hall",
            "Home",
            10.25,
        ),
    ]


def test_work_calendar_event_legs_export_with_event_name(tmp_path):
    code, result, err, transport = execute(tmp_path, event_sources(), event_drives())
    assert code == 0 and not err and result is not None
    assert [r["drive_id"] for r in result["business"]] == [10011, 10012]
    assert result["ambiguous"] == []
    csv_rows = list(csv.reader(io.StringIO(result["csv"])))
    assert [row[4] for row in csv_rows[1:]] == ['Work, "Meetup"'] * 2
    assert "2 work drives, 22.60 miles" in result["summary"]
    assert all(c["method"] == "GET" for c in transport.calls)


def test_uncertain_event_drives_use_existing_batch_confirmation(tmp_path):
    data, rows = event_sources(), event_drives()
    rows[0]["ending_location"] = "Unresolved event address"
    rows[1]["tag"] = "Personal"
    code, result, _, _ = execute(tmp_path, data, rows)
    assert code == 0 and result is not None and result["business"] == []
    assert [r["drive_id"] for r in result["ambiguous"]] == [10011, 10012]
    data["confirmed"] = [
        {"vin_suffix": RUSTLER[-4:], "drive_id": row["id"], "purpose": 'Work, "Meetup"'}
        for row in rows
    ]
    code, result, err, transport = execute(tmp_path, data, rows)
    assert code == 0 and not err and result is not None and result["ambiguous"] == []
    assert [r["drive_id"] for r in result["business"]] == [10011, 10012]
    assert list(csv.reader(io.StringIO(result["csv"])))[1][4] == 'Work, "Meetup"'
    assert all(c["method"] == "GET" for c in transport.calls)


@pytest.mark.parametrize("change", ["cancelled", "declined", "no_event", "outside_time"])
def test_event_destination_alone_is_not_work(tmp_path, change):
    data, rows = event_sources(), event_drives()
    event = data["work_events"][0]
    if change == "cancelled":
        data["work_events"] = [{"id": event["id"], "status": "cancelled"}]
    elif change == "declined":
        event["attendees"] = [{"self": True, "responseStatus": "declined"}]
    elif change == "no_event":
        data["work_events"] = []
    else:
        for field in ("start", "end"):
            event[field]["dateTime"] = event[field]["dateTime"].replace("11-10", "11-11")
    code, result, err, _ = execute(tmp_path, data, rows)
    assert code == 0 and not err and result is not None
    assert result["business"] == result["ambiguous"] == []


@pytest.mark.parametrize("change", ["timezone", "backwards", "purpose", "location"])
def test_invalid_work_event_fails_without_partial_report(tmp_path, change):
    data = event_sources()
    event = data["work_events"][0]
    if change == "timezone":
        event["start"]["dateTime"] = "2025-11-10T10:00:00"
    elif change == "backwards":
        event["end"] = event["start"]
    elif change == "purpose":
        event["summary"] = " "
    else:
        event["location"] = None
    code, result, err, transport = execute(tmp_path, data, event_drives())
    assert code == 1 and result is None and "Check INPUT_JSON" in err
    assert transport.calls == []


def test_all_day_event_drives_need_batch_confirmation(tmp_path):
    data = event_sources()
    event = data["work_events"][0]
    event["start"] = {"date": "2025-11-10"}
    event["end"] = {"date": "2025-11-11"}
    code, result, err, _ = execute(tmp_path, data, event_drives())
    assert code == 0 and not err and result is not None and result["business"] == []
    assert [r["drive_id"] for r in result["ambiguous"]] == [10011, 10012]
    data["confirmed"] = [
        {"vin_suffix": RUSTLER[-4:], "drive_id": 10011, "purpose": event["summary"]}
    ]
    code, result, err, _ = execute(tmp_path, data, event_drives())
    assert code == 0 and not err and result is not None
    assert [r["drive_id"] for r in result["business"]] == [10011]
    assert [r["drive_id"] for r in result["ambiguous"]] == [10012]


def test_missing_event_location_is_retained_in_batch(tmp_path):
    data = event_sources()
    del data["work_events"][0]["location"]
    code, result, err, _ = execute(tmp_path, data, event_drives())
    assert code == 0 and not err and result is not None and result["business"] == []
    assert [r["drive_id"] for r in result["ambiguous"]] == [10011, 10012]


def test_competing_event_drives_across_vehicles_require_confirmation(tmp_path):
    rows = event_drives()
    code, result, _, _ = execute(tmp_path, event_sources(), rows, second=[dict(rows[0], id=20011)])
    assert code == 0 and result is not None
    assert [r["drive_id"] for r in result["business"]] == [10012]
    assert len(result["ambiguous"]) == 2
    assert all("multiple drives" in r["reason"] for r in result["ambiguous"])


@pytest.mark.parametrize("change", ["no_booking", "wrong_flight", "wrong_date", "wrong_airport"])
def test_destination_alone_is_never_work(tmp_path, change):
    data = sources()
    if change == "no_booking":
        data["bookings"] = []
    else:
        field = {"wrong_flight": "number", "wrong_date": "date", "wrong_airport": "from"}[change]
        data["bookings"][0]["flights"][0][field] = "mismatch"
    code, result, _, transport = execute(tmp_path, data, round_trip())
    assert code == 0 and result is not None and result["business"] == []
    assert all(c["method"] == "GET" for c in transport.calls)


def test_trip_crossing_month_boundary_retains_return_and_midnight_pickup(tmp_path):
    data = sources()
    data["bookings"][0]["flights"][0]["date"] = "2025-10-31"
    data["tripit"]["AirObject"][0]["Segment"][0]["StartDateTime"]["date"] = "2025-10-31"
    data["tripit"]["AirObject"][0]["Segment"][1]["EndDateTime"]["time"] = "23:30:00"
    row = drive(
        10002,
        "2025-11-06T00:30:00-06:00",
        "2025-11-06T01:00:00-06:00",
        "Nashville International Airport",
        "Home",
    )
    code, result, _, _ = execute(tmp_path, data, [row])
    assert code == 0 and result is not None
    assert result["business"][0]["date"] == "2025-11-06"


def test_singleton_tripit_and_csv_formula_escaping(tmp_path):
    data = sources()
    data["bookings"][0]["purpose"] = '=HYPERLINK("https://example.invalid")'
    air = data["tripit"]["AirObject"][0]
    air["Segment"] = air["Segment"][0]
    data["tripit"]["AirObject"] = air
    rows = round_trip()[:1]
    rows[0]["starting_location"] = "@formula\nsecond line"
    code, result, _, _ = execute(tmp_path, data, rows)
    assert code == 0 and result is not None
    csv_rows = list(csv.reader(io.StringIO(result["csv"])))
    assert csv_rows[1][1] == "'@formula\nsecond line"
    assert csv_rows[1][4].startswith("'=HYPERLINK")


@pytest.mark.parametrize(
    "change", ["distance", "nan", "duplicate", "source", "timezone", "confirmation"]
)
def test_bad_data_fails_without_partial_csv(tmp_path, change):
    data, rows = sources(), round_trip()
    if change == "distance":
        rows[1]["distance"] = rows[1].pop("odometer_distance")
    elif change == "nan":
        rows[1]["odometer_distance"] = float("nan")
    elif change == "duplicate":
        rows.append(dict(rows[0], odometer_distance=99))
    elif change == "source":
        data["bookings"][0]["source"] = "personal-mail"
    elif change == "timezone":
        data["timezone"] = "missing/timezone"
    else:
        data["confirmed"] = [{"vin_suffix": "unknown", "drive_id": 10001, "purpose": "work"}]
    code, result, err, transport = execute(tmp_path, data, rows)
    assert code == 1 and result is None
    assert "Check INPUT_JSON" in err
    assert all(call["method"] == "GET" for call in transport.calls)


@pytest.mark.parametrize("chat,flag", [(READ_CHAT, True), (None, False)])
def test_owner_location_authority_required_before_vehicle_reads(tmp_path, chat, flag):
    code, result, _, transport = execute(
        tmp_path, sources(), round_trip(), chat=chat, include_location=flag
    )
    assert code == 4 and result is None and transport.calls == []


def test_provider_failure_is_not_an_empty_report(tmp_path):
    transport = FakeTransport({("GET", "/vehicles"): json_response({"error": "unavailable"}, 503)})
    rt, out, err = make_runtime(tmp_path, transport)
    path = tmp_path / "input.json"
    path.write_text(json.dumps(sources()))
    assert mileage.main([str(path), "--include-location"], runtime=rt) == 1
    assert out.getvalue() == "" and "503" in err.getvalue()
    assert len(transport.calls) == 1


def test_encoded_adapter_accepts_mileage_report():
    import base64

    adapter = load_script("tessie-ops", "tessie-argv")
    raw = json.dumps(
        {"script": "tessie-mileage", "argv": ["/tmp/input.json", "--include-location"]}
    )
    token = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    target, args = adapter.decode_argv(token)
    assert target.name == "tessie-mileage.py"
    assert args == ["/tmp/input.json", "--include-location"]


@pytest.mark.parametrize("provider_status,accepted", [(200, True), (200, False), (403, False)])
@pytest.mark.parametrize("context", ["trip", "event"])
def test_report_ids_feed_existing_tag_flow_and_csv_survives_tag_failure(
    tmp_path, provider_status, accepted, context
):
    data, rows = (
        (sources(), round_trip()) if context == "trip" else (event_sources(), event_drives())
    )
    expected_id = 10002 if context == "trip" else 10012
    rows[0]["tag"] = "Personal"
    code, result, _, transport = execute(tmp_path, data, rows)
    assert code == 0 and result is not None
    original_csv = result["csv"]
    assert [r["drive_id"] for r in result["business"]] == [expected_id]
    transport.routes[("POST", f"/{RUSTLER}/drives/set_tag")] = json_response(
        {"result": accepted}, provider_status
    )
    rt, out, _ = make_runtime(tmp_path, transport)
    command = load_script("tessie-ops", "tessie-command")
    args = [
        "set_drive_tag",
        "--vehicle",
        result["business"][0]["vehicle"]["alias"],
        "--drives",
        str(result["business"][0]["drive_id"]),
        "--tag",
        "Business",
    ]
    assert command.main(args + ["--dry-run"], runtime=rt) == 0
    plan = json.loads(out.getvalue())
    out.seek(0)
    out.truncate()
    assert command.main(args + ["--confirm", plan["confirm_with"]], runtime=rt) == (
        0 if accepted else 1
    )
    writes = [c for c in transport.calls if c["method"] == "POST"]
    assert len(writes) == 1
    assert json.loads(writes[0]["body"]) == {"drives": str(expected_id), "tag": "Business"}
    assert result["csv"] == original_csv
    if provider_status == 200:
        assert json.loads(out.getvalue())["status"] == ("accepted" if accepted else "failed")


def test_in_trip_drive_is_exported_only_after_batch_confirmation(tmp_path):
    data = sources()
    row = drive(
        10003, "2025-11-03T09:00:00-06:00", "2025-11-03T09:30:00-06:00", "Hotel", "Conference"
    )
    data["confirmed"] = [
        {"vin_suffix": RUSTLER[-4:], "drive_id": 10003, "purpose": "Work conference local drive"}
    ]
    code, result, _, transport = execute(tmp_path, data, [row])
    assert code == 0 and result is not None
    assert result["ambiguous"] == []
    assert result["business"][0]["drive_id"] == 10003
    assert "Work conference local drive" in result["csv"]
    assert all(c["method"] == "GET" for c in transport.calls)
