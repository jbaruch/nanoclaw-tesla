#!/usr/bin/env python3
"""Build an owner-only monthly work-mileage CSV from cached Tessie drives.

Usage: tessie-mileage.py INPUT_JSON --include-location
INPUT_JSON contains month (YYYY-MM), timezone (IANA), airport_locations (exact
Tessie location label -> IATA code), bookings, and tripit (TripIt JSON response).
work_events optionally contains Google Calendar event objects from the
verified work calendar: id, summary, start/end {dateTime with UTC offset or date}, and
location (exact Tessie label, or absent when unresolved). Retain calendar IDs
and original event evidence in the task. Omit cancelled, owner-declined, Travel
(title or category), all-day Home and week-number events. Preserve category when
the source supplies it. Only owner-organized or owner-accepted events establish attendance;
other invitations require batch confirmation. Preserve organizer.self and the
owner's attendee responseStatus. Event legs use the same six-hour windows as flights;
the event summary supplies purpose. All-day dates use the report timezone and
exclusive end date; their drives always need confirmation in the monthly batch.
After the monthly batch, optional confirmed is [{vin_suffix, drive_id, purpose}]
copied ONLY from explicit owner business decisions in this task. These decisions
may include ambiguous rows in the CSV; the file grants no tag-write authority.
bookings are active Navan confirmations extracted from port-mail-ingress for
baruchs@port.io, or the Navan browser behind the Port login. Each has source
(port-mail-ingress or navan-browser), account (baruchs@port.io), purpose, and
flights [{date: YYYY-MM-DD, from: IATA, to: IATA, airline: IATA, number: string}].
This is an extraction contract, NOT a Navan API schema; retain original mail or
browser evidence in the task. Personal mail/calendars and destination guesses
are not work evidence. Recognition requiring judgment belongs to the caller.

tripit uses live AirObject (singleton or list), trip_id, Segment (singleton or
list), StartDateTime/EndDateTime {date,time,utc_offset}, start_airport_code,
end_airport_code, marketing_airline_code, marketing_flight_number. An exact
Navan date/airports/flight match makes that TripIt trip work. Use the complete
trip, including flights outside the report month, to retain both airport legs.
Airport legs must end within six hours before departure or start within six
hours after arrival, at the exact mapped airport. Multiple candidates for a
flight leg, conflicting trips, unknown locations and existing non-Business
tags require confirmation. Drives between flights of a closed round trip enter
the batch: timing alone cannot prove that a drive was within the owner's trip
rather than someone else's personal use of a vehicle left at home. Confirmed
trip drives are work under the Navan policy. Other drives are omitted.
No natural-language location matching.

Reads all eligible vehicles via the existing host broker. Tessie defaults to
miles; odometer_distance is used without conversion. Local drive start dates
select the exported month, after checking competitors across the supplied work
contexts. Read history from epoch through six hours after the later of month end
or the last context's arrival/end: an outbound competitor may start arbitrarily
early and still end inside a departure window. Each read limits results to 100
for the host's 1 MiB response cap; full windows are subdivided until complete.
An indivisible full window fails closed. Duplicate drive IDs count once; conflicting
duplicates or malformed provider rows fail the whole report, never partial CSV.
Stdout JSON: {month, csv, summary, business, ambiguous}. business/ambiguous rows
carry vehicle (alias, vin_suffix), drive_id, date, from, to, miles, purpose;
ambiguous adds reason. CSV columns: date,from,to,miles,purpose,vehicle. Text cells
are escaped for spreadsheet formulas. summary is one line. No provider writes,
CSV file writes, approvals, scheduling or persistent state. Apply business IDs
through the existing confirmed set_drive_tag flow; ambiguous IDs only after an
explicit owner decision. Exit 0 success, 1 invalid input/provider failure,
2 usage, 4 owner/location denied. No automatic retry or HTTP fallback.

Provider shapes: https://developer.tessie.com/reference/get-drives and
https://tripit.github.io/api/doc/v1/ (AirObject). Tagging contract:
https://developer.tessie.com/reference/set-drive-tag (tag: Business).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import sys
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from tessie_actions import fetch_inventory, read_vehicle
from tessie_cli import Runtime, guarded
from tessie_core import EXIT_DENIED, TessieError, emit
from tessie_policy import ROLE_OWNER, eligible_entries, select_vehicle


def objects(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else [value]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("expected provider objects")
    return rows


def flight_key(segment: dict[str, Any]) -> tuple[str, ...]:
    return (
        segment["StartDateTime"]["date"],
        segment["start_airport_code"],
        segment["end_airport_code"],
        segment["marketing_airline_code"],
        str(segment["marketing_flight_number"]),
    )


def flight_time(value: dict[str, str]) -> datetime:
    return datetime.fromisoformat(value["date"] + "T" + value["time"] + value["utc_offset"])


def work_trips(data: dict[str, Any]) -> list[dict[str, Any]]:
    if "Error" in data["tripit"]:
        raise ValueError("TripIt source returned an error; refresh the source")
    booked: dict[tuple[str, ...], set[str]] = {}
    for booking in objects(data["bookings"]):
        if booking["source"] not in {"port-mail-ingress", "navan-browser"} or (
            booking["account"] != "baruchs@port.io"
        ):
            raise ValueError("unsupported work evidence")
        purpose = booking["purpose"]
        if not isinstance(purpose, str) or not purpose.strip():
            raise ValueError("missing trip purpose")
        for flight in objects(booking["flights"]):
            key = tuple(flight[field] for field in ("date", "from", "to", "airline", "number"))
            if not all(isinstance(part, str) and part for part in key):
                raise ValueError("invalid booking flight")
            booked.setdefault(key, set()).add(purpose)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for air in objects(data["tripit"].get("AirObject", [])):
        segments = objects(air["Segment"])
        for segment in segments:
            if not all(
                isinstance(segment.get(field), str) and re.fullmatch(r"[A-Z]{3}", segment[field])
                for field in ("start_airport_code", "end_airport_code")
            ):
                raise ValueError("invalid TripIt airport code")
        grouped.setdefault(str(air["trip_id"]), []).extend(segments)
    trips = []
    for segments in grouped.values():
        purposes = set().union(*(booked.get(flight_key(s), set()) for s in segments))
        if not purposes:
            continue
        segments.sort(key=lambda s: flight_time(s["StartDateTime"]))
        first, last = segments[0], segments[-1]
        departure = flight_time(first["StartDateTime"])
        arrival = flight_time(last["EndDateTime"])
        if arrival <= departure:
            raise ValueError("invalid trip times")
        trips.append(
            {
                "purpose": " / ".join(sorted(purposes)),
                "departure": departure,
                "arrival": arrival,
                "origin": first["start_airport_code"],
                "destination": last["end_airport_code"],
                "closed": len(segments) > 1
                and first["start_airport_code"] == last["end_airport_code"],
            }
        )
    return trips


def spreadsheet_text(value: str) -> str:
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def report(data: dict[str, Any], rt: Runtime, allowlist: Any) -> dict[str, Any]:
    if not isinstance(data, dict) or not isinstance(data.get("tripit"), dict):
        raise ValueError("invalid report input")
    if not re.fullmatch(r"\d{4}-\d{2}", data["month"]):
        raise ValueError("invalid month")
    zone = ZoneInfo(data["timezone"])
    start = datetime.strptime(data["month"], "%Y-%m").replace(tzinfo=zone)
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    airports = data["airport_locations"]
    if not isinstance(airports, dict) or not all(
        isinstance(label, str) and isinstance(code, str) and re.fullmatch(r"[A-Z]{3}", code)
        for label, code in airports.items()
    ):
        raise ValueError("invalid airport locations")
    contexts = work_trips(data)
    for event in objects(data.get("work_events", [])):
        if event.get("status") == "cancelled" or any(
            attendee.get("self") and attendee.get("responseStatus") == "declined"
            for attendee in objects(event.get("attendees", []))
        ):
            continue
        if not all(isinstance(event[key], str) and event[key].strip() for key in ("id", "summary")):
            raise ValueError("missing work event identity or purpose")
        all_day = "date" in event["start"]
        title = event["summary"].strip().casefold()
        category = event.get("category", "")
        if not isinstance(category, str):
            raise ValueError("invalid work event category")
        if (
            "travel" in title
            or "travel" in category.casefold()
            or (all_day and title == "home")
            or re.search(r"\bweek(?:\s+number)?\s*#?\s*\d+\b", title)
        ):
            continue
        organizer = event.get("organizer", {})
        if not isinstance(organizer, dict):
            raise ValueError("invalid work event organizer")
        if all_day:
            departure = datetime.strptime(event["start"]["date"], "%Y-%m-%d").replace(tzinfo=zone)
            arrival = datetime.strptime(event["end"]["date"], "%Y-%m-%d").replace(tzinfo=zone)
        else:
            departure = datetime.fromisoformat(event["start"]["dateTime"])
            arrival = datetime.fromisoformat(event["end"]["dateTime"])
        location = event.get("location", "")
        if (
            departure.utcoffset() is None
            or arrival.utcoffset() is None
            or arrival <= departure
            or not isinstance(location, str)
        ):
            raise ValueError("invalid work event time or location")
        contexts.append(
            {
                "purpose": event["summary"],
                "departure": departure,
                "arrival": arrival,
                "location": location,
                "closed": all_day,
                "accepted": organizer.get("self") is True
                or any(
                    attendee.get("self") is True and attendee.get("responseStatus") == "accepted"
                    for attendee in objects(event.get("attendees", []))
                ),
            }
        )
    inventory = fetch_inventory(rt.client)
    candidates = []
    seen = {}
    for entry in eligible_entries(allowlist, inventory):
        vehicle = select_vehicle(entry.vin, allowlist, inventory)
        windows = [
            (
                0,
                int(
                    (max([end] + [c["arrival"] for c in contexts]) + timedelta(hours=6)).timestamp()
                ),
            )
        ]
        drives = []
        while windows:
            lower, upper = windows.pop()
            payload = read_vehicle(
                rt.client,
                vehicle,
                "drives",
                include_location=True,
                query={"from": lower, "to": upper, "limit": 100},
            )["data"]
            rows = objects(payload["results"])
            if len(rows) >= 100:
                if upper - lower <= 1:
                    raise ValueError("drive history window cannot establish complete coverage")
                middle = (lower + upper) // 2
                # Overlap boundaries; the existing ID check removes duplicates.
                windows.extend([(middle, upper), (lower, middle)])
            else:
                drives.extend(rows)
        for drive in drives:
            drive_id = drive["id"]
            if type(drive_id) is not int or drive_id <= 0:
                raise ValueError("invalid drive id")
            identity = (vehicle.vin, drive_id)
            if identity in seen:
                if seen[identity] != drive:
                    raise ValueError("conflicting duplicate drive")
                continue
            seen[identity] = drive
            begin, finish, miles = (
                drive[k] for k in ("started_at", "ended_at", "odometer_distance")
            )
            if any(
                type(v) not in (int, float) or not math.isfinite(v) for v in (begin, finish, miles)
            ):
                raise ValueError("invalid drive measurements")
            if finish <= begin or miles < 0:
                raise ValueError("invalid drive measurements")
            begin = datetime.fromtimestamp(begin, zone)
            finish = datetime.fromtimestamp(finish, zone)
            origin, destination = drive["starting_location"], drive["ending_location"]
            if not all(isinstance(v, str) for v in (origin, destination)):
                raise ValueError("invalid drive locations")
            matches, possible = [], []
            for index, context in enumerate(contexts):
                outbound = timedelta(0) <= context["departure"] - finish <= timedelta(hours=6)
                inbound = timedelta(0) <= begin - context["arrival"] <= timedelta(hours=6)
                within = (
                    context["closed"]
                    and context["departure"] <= begin < finish <= context["arrival"]
                )
                if outbound or inbound or within:
                    possible.append(context["purpose"])
                destination_matches = (
                    bool(context["location"]) and destination == context["location"]
                    if "location" in context
                    else airports.get(destination) == context["origin"]
                )
                origin_matches = (
                    bool(context["location"]) and origin == context["location"]
                    if "location" in context
                    else airports.get(origin) == context["destination"]
                )
                if outbound and destination_matches:
                    matches.append((index, "departure"))
                elif inbound and origin_matches:
                    matches.append((index, "return"))
                elif within:
                    matches.append((index, "within"))
            if not possible:
                continue
            row = {
                "vehicle": {"alias": vehicle.alias, "vin_suffix": vehicle.vin_suffix},
                "drive_id": drive_id,
                "date": begin.date().isoformat(),
                "from": origin,
                "to": destination,
                "miles": round(miles, 2),
                "purpose": " / ".join(sorted(set(possible))),
            }
            reason = None
            if len(matches) != 1:
                reason = "uncertain trip, event or location match"
            elif "location" in contexts[matches[0][0]] and not contexts[matches[0][0]]["accepted"]:
                reason = "event attendance requires confirmation"
            elif matches[0][1] == "within" or (
                "location" in contexts[matches[0][0]] and contexts[matches[0][0]]["closed"]
            ):
                reason = "drive during trip or all-day event needs location confirmation"
            elif drive.get("tag") and drive["tag"] != "Business":
                reason = "existing tag requires confirmation"
            candidates.append((row, matches, reason))
    decisions = {}
    for decision in objects(data.get("confirmed", [])):
        key = (decision["vin_suffix"], decision["drive_id"])
        if (
            key in decisions
            or not isinstance(decision["purpose"], str)
            or not decision["purpose"].strip()
        ):
            raise ValueError("invalid confirmation")
        decisions[key] = decision["purpose"]
    business, ambiguous = [], []
    for row, matches, reason in candidates:
        if data["month"] != row["date"][:7]:
            continue
        if len(matches) == 1 and matches[0][1] != "within":
            if sum(matches[0] in other for _, other, _ in candidates) > 1:
                reason = "multiple drives for the same work leg"
        decision = decisions.pop((row["vehicle"]["vin_suffix"], row["drive_id"]), None)
        if decision is not None:
            row["purpose"] = decision
            business.append(row)
        elif reason:
            ambiguous.append({**row, "reason": reason})
        else:
            row["purpose"] = contexts[matches[0][0]]["purpose"]
            business.append(row)
    if decisions:
        raise ValueError("confirmation does not identify a report candidate")
    business.sort(key=lambda row: (row["date"], row["vehicle"]["alias"], row["drive_id"]))
    ambiguous.sort(key=lambda row: (row["date"], row["vehicle"]["alias"], row["drive_id"]))
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["date", "from", "to", "miles", "purpose", "vehicle"])
    for row in business:
        writer.writerow(
            [row["date"]]
            + [spreadsheet_text(row[key]) for key in ("from", "to")]
            + [
                f"{row['miles']:.2f}",
                spreadsheet_text(row["purpose"]),
                spreadsheet_text(row["vehicle"]["alias"]),
            ]
        )
    total = sum(row["miles"] for row in business)
    return {
        "month": data["month"],
        "csv": output.getvalue(),
        "summary": f"{data['month']}: {len(business)} work drives, {total:.2f} miles; "
        f"{len(ambiguous)} drives need confirmation; Tessie tags not applied by this report.",
        "business": business,
        "ambiguous": ambiguous,
    }


def main(argv: Sequence[str] | None = None, *, runtime: Runtime | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export monthly work mileage")
    parser.add_argument("input", type=Path)
    parser.add_argument("--include-location", action="store_true")
    args = parser.parse_args(argv)
    rt = runtime if runtime is not None else Runtime()

    def body() -> int:
        allowlist = rt.load()
        rt.authorize(allowlist, ROLE_OWNER, "work mileage locations")
        if not args.include_location:
            raise TessieError(
                "Re-run with --include-location in an owner chat.", exit_code=EXIT_DENIED
            )
        try:
            data = json.loads(args.input.read_text(encoding="utf-8"))
            result = report(data, rt, allowlist)
        except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
            raise TessieError(
                "Cannot build mileage report. Check INPUT_JSON against the script contract "
                "and refresh complete TripIt/Tessie/calendar source data; no tags were changed.",
                code="invalid_mileage_data",
            ) from exc
        emit(result, rt.out)
        return 0

    return guarded(rt, body)


if __name__ == "__main__":
    sys.exit(main())
