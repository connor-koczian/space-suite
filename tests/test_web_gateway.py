"""Unit tests for SpaceSuite Unified Mission Control Web Gateway."""

from __future__ import annotations

import io
import json
from http import HTTPStatus
from unittest.mock import MagicMock

import pytest

from space_suite.iss.models import ObserverCoords
from space_suite.iss.notifier import UbuntuNotifier
from space_suite.iss.web_server import TelemetryState
from space_suite.lander.web_server import LanderSimulationState
from space_suite.launch.client import LaunchClient
from space_suite.web_gateway import UnifiedGatewayHandler


class DummyRequest:
    def __init__(self, data: bytes = b"") -> None:
        self.rfile = io.BytesIO(data)
        self.wfile = io.BytesIO()

    def makefile(self, *args, **kwargs):
        if "r" in args[0]:
            return self.rfile
        return self.wfile

    def sendall(self, data: bytes) -> None:
        self.wfile.write(data)


@pytest.fixture
def gateway_handler():
    observer = ObserverCoords(51.5074, -0.1278, "London")
    notifier = MagicMock(spec=UbuntuNotifier)
    iss_state = TelemetryState(observer, notifier)
    launch_client = MagicMock(spec=LaunchClient)
    launch_client.fetch_upcoming.return_value = []
    lander_sim = LanderSimulationState()

    UnifiedGatewayHandler.iss_state = iss_state
    UnifiedGatewayHandler.launch_client = launch_client
    UnifiedGatewayHandler.lander_sim = lander_sim

    return UnifiedGatewayHandler


def build_handler(handler_cls, path: str, method: str = "GET", body: bytes = b""):
    req_line = f"{method} {path} HTTP/1.1\r\nHost: localhost:8055\r\nContent-Length: {len(body)}\r\n\r\n".encode()
    raw = req_line + body
    req = DummyRequest(raw)
    handler = handler_cls(req, ("127.0.0.1", 12345), MagicMock())
    return handler, req.wfile.getvalue()


def test_gateway_serves_hub(gateway_handler):
    _, response = build_handler(gateway_handler, "/")
    assert b"200 OK" in response
    assert b"text/html" in response
    assert b"SpaceSuite" in response


def test_gateway_serves_iss(gateway_handler):
    _, response = build_handler(gateway_handler, "/iss")
    assert b"200 OK" in response
    assert b"text/html" in response


def test_gateway_serves_launch(gateway_handler):
    _, response = build_handler(gateway_handler, "/launch")
    assert b"200 OK" in response
    assert b"text/html" in response


def test_gateway_serves_lander(gateway_handler):
    _, response = build_handler(gateway_handler, "/lander")
    assert b"200 OK" in response
    assert b"text/html" in response


def test_gateway_serves_leaflet_assets(gateway_handler):
    _, res_js = build_handler(gateway_handler, "/leaflet.js")
    assert b"200 OK" in res_js

    _, res_css = build_handler(gateway_handler, "/leaflet.css")
    assert b"200 OK" in res_css


def test_gateway_handles_favicon_and_images_no_content(gateway_handler):
    _, res_fav = build_handler(gateway_handler, "/favicon.ico")
    assert b"204 No Content" in res_fav

    _, res_img = build_handler(gateway_handler, "/images/layers.png")
    assert b"204 No Content" in res_img


def test_gateway_iss_telemetry_api(gateway_handler):
    _, response = build_handler(gateway_handler, "/api/iss/telemetry")
    assert b"200 OK" in response
    assert b"application/json" in response


def test_gateway_launch_api(gateway_handler):
    _, response = build_handler(gateway_handler, "/api/launches?search=SpaceX")
    assert b"200 OK" in response
    assert b"application/json" in response


def test_gateway_lander_telemetry_api(gateway_handler):
    _, response = build_handler(gateway_handler, "/api/lander/telemetry")
    assert b"200 OK" in response
    assert b"application/json" in response


def test_gateway_lander_action_post(gateway_handler):
    body = json.dumps({"action": "reset"}).encode("utf-8")
    _, response = build_handler(gateway_handler, "/api/action", method="POST", body=body)
    assert b"200 OK" in response
    assert b"ok" in response


def test_gateway_404_not_found_safe_logging(gateway_handler):
    # This verifies that 404 does not crash log_message with TypeError: argument of type 'HTTPStatus' is not iterable
    _, response = build_handler(gateway_handler, "/invalid_random_path_12345")
    assert b"404" in response


def test_log_message_exception_safety(gateway_handler):
    # Construct dummy handler without network socket
    dummy = gateway_handler.__new__(gateway_handler)
    dummy.client_address = ("127.0.0.1", 12345)

    # Calling with HTTPStatus enum as first argument must not raise TypeError
    dummy.log_message("code %d, message %s", HTTPStatus.NOT_FOUND, "Path not found")

    # Calling with routine api request must suppress safely
    dummy.log_message('"%s" %s %s', "GET /api/iss/telemetry HTTP/1.1", "200", "-")
