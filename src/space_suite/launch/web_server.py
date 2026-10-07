"""Lightweight local web server for the SpaceX & Rocket Mission Control dashboard."""

from __future__ import annotations

import json
import logging
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from space_suite.launch.client import LaunchAPIError, LaunchClient
from space_suite.launch.models import LaunchItem

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "web"
SHARED_STATIC_DIR = Path(__file__).parent.parent / "iss" / "web"


def serialize_launch(launch: LaunchItem) -> dict[str, Any]:
    return {
        "id": launch.id,
        "name": launch.name,
        "status_name": launch.status_name,
        "status_abbrev": launch.status_abbrev,
        "net_time": launch.net_time.isoformat(),
        "provider_name": launch.provider_name,
        "provider_type": launch.provider_type,
        "rocket": {
            "name": launch.rocket.name,
            "full_name": launch.rocket.full_name,
            "family": launch.rocket.family,
            "variant": launch.rocket.variant,
        },
        "pad": {
            "name": launch.pad.name,
            "location_name": launch.pad.location_name,
            "country_code": launch.pad.country_code,
            "latitude": launch.pad.latitude,
            "longitude": launch.pad.longitude,
            "map_url": launch.pad.map_url,
        },
        "mission": (
            {
                "name": launch.mission.name,
                "description": launch.mission.description,
                "mission_type": launch.mission.mission_type,
                "orbit_name": launch.mission.orbit_name,
                "orbit_abbrev": launch.mission.orbit_abbrev,
            }
            if launch.mission
            else None
        ),
        "is_spacex": launch.is_spacex,
        "is_starship": launch.is_starship,
        "livestream_url": launch.livestream_url,
        "image_url": launch.image_url,
    }


class LaunchWebHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for Launch Mission Control dashboard."""

    client: LaunchClient

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        pass

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path in ("/", "/index.html"):
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            index_path = STATIC_DIR / "index.html"
            self.wfile.write(index_path.read_bytes())
        elif path == "/leaflet.js":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/javascript")
            self.end_headers()
            self.wfile.write((SHARED_STATIC_DIR / "leaflet.js").read_bytes())
        elif path == "/leaflet.css":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/css")
            self.end_headers()
            self.wfile.write((SHARED_STATIC_DIR / "leaflet.css").read_bytes())
        elif path == "/api/launches":
            query = urllib.parse.parse_qs(parsed_url.query)
            search_param = query.get("search", [None])[0]

            try:
                launches = self.client.fetch_upcoming(search=search_param, limit=10)
                payload = json.dumps(
                    {
                        "status": "online",
                        "count": len(launches),
                        "launches": [serialize_launch(l) for l in launches],
                    }
                )
            except LaunchAPIError as err:
                payload = json.dumps(
                    {"status": "error", "error": str(err), "launches": []}
                )

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(payload.encode("utf-8"))
        else:
            super().do_GET()


def launch_web_server(
    search: str | None = "SpaceX",
    port: int = 8056,
    open_browser: bool = True,
) -> None:
    """Start local launch mission control web server and launch browser."""
    client = LaunchClient()

    class BoundHandler(LaunchWebHandler):
        pass

    BoundHandler.client = client

    url = f"http://127.0.0.1:{port}"
    server = ThreadingHTTPServer(("127.0.0.1", port), BoundHandler)

    print(f"\n🚀  SpaceX & Rocket Launch Mission Control is live at: {url}")
    print("Press Ctrl+C to terminate the server.\n")

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down launch mission control server...")
    finally:
        client.close()
        server.server_close()
        print("Server shutdown complete.")
