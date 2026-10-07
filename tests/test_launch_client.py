"""Unit tests for Launch Library 2 client and payload parsing."""

from datetime import UTC, datetime

from space_suite.launch.client import LaunchClient


def test_parse_launch_payload():
    raw_item = {
        "id": "1111-2222-3333",
        "name": "Falcon 9 Block 5 | Crew-9",
        "status": {"name": "Go for Launch", "abbrev": "Go"},
        "net": "2026-10-15T18:30:00Z",
        "launch_service_provider": {"name": "SpaceX", "type": "Commercial"},
        "rocket": {
            "configuration": {
                "name": "Falcon 9",
                "full_name": "Falcon 9 Block 5",
                "family": "Falcon",
                "variant": "Block 5",
            }
        },
        "pad": {
            "name": "Launch Complex 39A",
            "location": {"name": "Kennedy Space Center, FL, USA"},
            "country_code": "USA",
            "latitude": "28.6083",
            "longitude": "-80.6043",
            "map_url": "https://maps.google.com/?q=28.6083,-80.6043",
        },
        "mission": {
            "name": "Crew-9",
            "description": "Commercial Crew rotation mission to the ISS.",
            "type": "Human Spaceflight",
            "orbit": {"name": "Low Earth Orbit", "abbrev": "LEO"},
        },
        "vid_urls": [{"url": "https://youtube.com/live/crew9"}],
    }

    launch = LaunchClient._parse_launch(raw_item)
    assert launch.id == "1111-2222-3333"
    assert launch.name == "Falcon 9 Block 5 | Crew-9"
    assert launch.status_name == "Go for Launch"
    assert launch.provider_name == "SpaceX"
    assert launch.rocket.name == "Falcon 9"
    assert launch.pad.name == "Launch Complex 39A"
    assert launch.pad.latitude == 28.6083
    assert launch.mission is not None
    assert launch.mission.name == "Crew-9"
    assert launch.livestream_url == "https://youtube.com/live/crew9"
    assert launch.net_time == datetime(2026, 10, 15, 18, 30, 0, tzinfo=UTC)
