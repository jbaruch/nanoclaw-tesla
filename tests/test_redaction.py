"""Location redaction: coordinates and street addresses never leave the decoder."""

from __future__ import annotations

import json

from support import ADDRESS, LAT, LON, state_payload
from tessie_core import redact_location


def test_coordinates_and_addresses_are_dropped_recursively() -> None:
    clean, dropped = redact_location(state_payload())
    text = json.dumps(clean)
    assert str(LAT) not in text and str(LON) not in text and ADDRESS not in text
    for key in ("latitude", "longitude", "native_latitude", "active_route_destination"):
        assert key not in text
    assert dropped >= 6


def test_saved_place_labels_and_street_addresses_are_removed_from_history() -> None:
    clean, _ = redact_location(
        {
            "results": [
                {
                    "starting_location": ADDRESS,
                    "starting_saved_location": "Home",
                    "ending_saved_location": "Work",
                    "saved_location": "Private clinic",
                    "ending_location": ADDRESS,
                    "distance": 12.3,
                }
            ]
        }
    )
    assert clean == {"results": [{"distance": 12.3}]}


def test_non_location_state_is_untouched() -> None:
    payload = {"vehicle_state": {"locked": True}, "charge_state": {"battery_level": 64}}
    clean, dropped = redact_location(payload)
    assert clean == payload
    assert dropped == 0


def test_redaction_does_not_mutate_its_input() -> None:
    payload = state_payload()
    redact_location(payload)
    assert payload["drive_state"]["latitude"] == LAT


def test_explicit_coordinate_containers_and_saved_places_are_removed() -> None:
    payload = {
        "results": [
            {
                "coordinates": [LAT, LON],
                "saved_place": "Synthetic private clinic",
                "savedPlace": "Synthetic private home",
                "starting_saved_place": "Synthetic private office",
                "current-position": {"x": LAT, "y": LON},
                "geoLocation": [LAT, LON],
                "geometry": {"type": "Point", "value": [LAT, LON]},
                "distance": 12.3,
            }
        ]
    }
    clean, dropped = redact_location(payload)
    assert clean == {"results": [{"distance": 12.3}]}
    assert dropped == 7
    assert payload["results"][0]["coordinates"] == [LAT, LON]
