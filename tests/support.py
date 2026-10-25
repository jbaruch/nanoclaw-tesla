"""Synthetic Tessie fixtures, fake transport and runtime builders.

Everything here is built programmatically: synthetic VINs, a frozen clock and
canned JSON. Nothing touches the network, the real allowlist or a real token.
"""

from __future__ import annotations

import importlib.util
import io
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from types import ModuleType
from typing import Any

from tessie_cli import Runtime
from tessie_core import HttpResponse, TessieClient

ROOT = Path(__file__).resolve().parent.parent
NOW = 1_800_000_000.0  # frozen "now" (epoch seconds) for every time-dependent test

OWNER_CHAT = "tg:owner-chat"
CONTROL_CHAT = "tg:control-chat"
READ_CHAT = "tg:read-chat"
STRANGER_CHAT = "tg:stranger-chat"

RUSTLER = "SYNTH000000001832"  # OWNER, active, lychee
BRADBURY = "SYNTH000000003496"  # OWNER, active, cybertruck
POWERSLAVE = "SYNTH000000007263"  # DRIVER, asleep, model3
BLUE_ROCKET = "SYNTH000000005802"  # DRIVER, inactive
UNNAMED = "SYNTH000000009999"  # null access_type, inactive

LAT, LON = 41.123456, -87.654321
ADDRESS = "1 Synthetic Way, Nowhere"


def vehicle_row(
    vin: str,
    name: str | None,
    access_type: str | None,
    is_active: bool | None,
    car_type: str = "model3",
) -> dict[str, Any]:
    return {
        "vin": vin,
        "access_type": access_type,
        "is_active": is_active,
        "last_state": {
            "display_name": name,
            "vehicle_config": {"car_type": car_type},
            "drive_state": {"latitude": LAT, "longitude": LON, "native_latitude": LAT},
        },
    }


def inventory_payload() -> dict[str, Any]:
    return {
        "results": [
            vehicle_row(RUSTLER, "The Rustler", "OWNER", True, "lychee"),
            vehicle_row(BRADBURY, "Bradbury", "OWNER", True, "cybertruck"),
            vehicle_row(POWERSLAVE, "Powerslave", "DRIVER", False, "model3"),
            vehicle_row(BLUE_ROCKET, "Blue Rocket", "DRIVER", False, "lychee"),
            vehicle_row(UNNAMED, None, None, False),
        ]
    }


def state_payload(
    *,
    locked: bool = True,
    climate_on: bool = False,
    driver_temp: float = 21.0,
    charging_state: str = "Disconnected",
    charge_limit: int = 80,
    battery_level: int = 64,
    stamp_s: float = NOW,
) -> dict[str, Any]:
    ms = int(stamp_s * 1000)
    return {
        "display_name": "The Rustler",
        "vehicle_state": {"locked": locked, "timestamp": ms, "vehicle_name": "The Rustler"},
        "climate_state": {
            "is_climate_on": climate_on,
            "driver_temp_setting": driver_temp,
            "timestamp": ms,
        },
        "charge_state": {
            "charging_state": charging_state,
            "charge_limit_soc": charge_limit,
            "battery_level": battery_level,
            "timestamp": ms,
        },
        "drive_state": {
            "latitude": LAT,
            "longitude": LON,
            "native_latitude": LAT,
            "native_longitude": LON,
            "active_route_destination": ADDRESS,
            "active_route_latitude": LAT,
            "shift_state": None,
            "timestamp": ms,
        },
        "vehicle_config": {"car_type": "lychee"},
    }


def json_response(
    payload: Any, status: int = 200, headers: Mapping[str, str] | None = None
) -> HttpResponse:
    return HttpResponse(status, dict(headers or {}), json.dumps(payload).encode("utf-8"))


Route = HttpResponse | Callable[[], HttpResponse] | list[HttpResponse]


class FakeTransport:
    """Records every request; answers from a (method, path) table or fails the test."""

    def __init__(self, routes: Mapping[tuple[str, str], Route] | None = None) -> None:
        self.routes: dict[tuple[str, str], Route] = dict(routes or {})
        self.calls: list[dict[str, Any]] = []

    def send(
        self,
        method: str,
        url: str,
        *,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> HttpResponse:
        from urllib.parse import parse_qs, urlsplit

        parts = urlsplit(url)
        self.calls.append(
            {
                "method": method,
                "url": url,
                "host": f"{parts.scheme}://{parts.netloc}",
                "path": parts.path,
                "query": {k: v[0] for k, v in parse_qs(parts.query).items()},
                "headers": dict(headers),
                "body": body,
                "timeout": timeout,
            }
        )
        route = self.routes.get((method, parts.path))
        if route is None:
            raise AssertionError(f"unexpected request {method} {parts.path}")
        if isinstance(route, list):
            return route.pop(0)
        return route() if callable(route) else route

    def paths(self, method: str | None = None) -> list[str]:
        return [c["path"] for c in self.calls if method is None or c["method"] == method]


def standard_transport(
    *,
    status: str = "awake",
    state: dict[str, Any] | None = None,
    command_result: bool = True,
) -> FakeTransport:
    """A healthy account: inventory, status, state and lock/climate/etc. commands."""
    routes: dict[tuple[str, str], Route] = {
        ("GET", "/vehicles"): json_response(inventory_payload()),
        ("GET", f"/{RUSTLER}/status"): json_response({"status": status}),
        ("GET", f"/{RUSTLER}/state"): json_response(state or state_payload()),
        ("GET", f"/{RUSTLER}/battery"): json_response(
            {"battery_level": 64, "latitude": LAT, "longitude": LON}
        ),
        ("GET", f"/{RUSTLER}/location"): json_response(
            {"latitude": LAT, "longitude": LON, "address": ADDRESS, "saved_location": "Home"}
        ),
        ("GET", f"/{RUSTLER}/drivers"): json_response({"results": [{"name": "Synthetic Driver"}]}),
        ("GET", f"/{RUSTLER}/drives"): json_response(
            {
                "results": [
                    {
                        "id": 10001,
                        "starting_location": ADDRESS,
                        "starting_saved_location": "Home",
                        "starting_latitude": LAT,
                        "ending_location": ADDRESS,
                        "ending_saved_location": "Work",
                        "ending_longitude": LON,
                        "distance": 12.3,
                    }
                ]
            }
        ),
        ("POST", f"/{RUSTLER}/drives/set_tag"): json_response({"result": True}),
    }
    for op in (
        "lock",
        "unlock",
        "start_climate",
        "stop_climate",
        "set_temperatures",
        "start_charging",
        "stop_charging",
        "set_charge_limit",
        "share",
        "flash",
    ):
        routes[("POST", f"/{RUSTLER}/command/{op}")] = json_response({"result": command_result})
    return FakeTransport(routes)


def write_environ(path: Path, chat: str | None, extra: Mapping[str, str] | None = None) -> Path:
    """A stand-in for /proc/1/environ: NUL-separated KEY=VALUE pairs."""
    items = {"PATH": "/usr/bin", **(extra or {})}
    if chat is not None:
        items["NANOCLAW_CHAT_JID"] = chat
    path.write_bytes(b"\0".join(f"{k}={v}".encode() for k, v in items.items()) + b"\0")
    return path


def allowlist_document(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema_version": 1,
        "owner_chats": [OWNER_CHAT],
        "control_chats": [CONTROL_CHAT],
        "read_chats": [READ_CHAT],
        "default_vehicle": "The Rustler",
        "vehicles": [
            {"vin": RUSTLER, "alias": "The Rustler"},
            {"vin": BRADBURY, "alias": "Bradbury"},
        ],
    }
    document.update(overrides)
    return document


def write_allowlist(path: Path, document: Mapping[str, Any] | None = None) -> Path:
    path.write_text(json.dumps(document if document is not None else allowlist_document()))
    return path


def make_runtime(
    tmp_path: Path,
    transport: FakeTransport,
    *,
    chat: str | None = OWNER_CHAT,
    document: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[Runtime, io.StringIO, io.StringIO]:
    out, err = io.StringIO(), io.StringIO()
    runtime = Runtime(
        client=TessieClient(transport),
        allowlist_path=write_allowlist(tmp_path / "allowlist.json", document),
        environ_path=write_environ(tmp_path / "environ", chat),
        env=dict(env or {}),
        now=lambda: NOW,
        out=out,
        err=err,
    )
    return runtime, out, err


def load_script(skill: str, name: str) -> ModuleType:
    """Import a hyphenated CLI script (`tessie-read.py`) as a module."""
    path = ROOT / "skills" / skill / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"script_{name.replace('-', '_')}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
