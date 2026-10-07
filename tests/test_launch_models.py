"""Unit tests for rocket launch models and countdown calculation."""

from datetime import UTC, datetime, timedelta

import pytest

from space_suite.launch.models import LaunchItem, MissionInfo, PadInfo, RocketInfo


@pytest.fixture
def sample_launch():
    net = datetime.now(UTC) + timedelta(days=2, hours=3, minutes=15, seconds=30)
    return LaunchItem(
        id="sample-123",
        name="Falcon 9 Block 5 | Starlink Group 10-1",
        status_name="Go for Launch",
        status_abbrev="Go",
        net_time=net,
        provider_name="SpaceX",
        provider_type="Commercial",
        rocket=RocketInfo(
            name="Falcon 9",
            family="Falcon",
            variant="Block 5",
            full_name="Falcon 9 Block 5",
        ),
        pad=PadInfo(
            name="Space Launch Complex 40",
            location_name="Cape Canaveral SFS, FL, USA",
            country_code="USA",
            latitude=28.5619,
            longitude=-80.5774,
        ),
        mission=MissionInfo(
            name="Starlink Group 10-1",
            description="Starlink v2 Mini broadband satellites.",
            mission_type="Communications",
            orbit_name="Low Earth Orbit",
            orbit_abbrev="LEO",
        ),
        vid_urls=["https://www.youtube.com/watch?v=sample"],
    )


def test_launch_is_spacex(sample_launch):
    assert sample_launch.is_spacex is True
    assert sample_launch.is_starship is False


def test_starship_flag():
    net = datetime.now(UTC) + timedelta(days=1)
    starship_launch = LaunchItem(
        id="starship-ift-5",
        name="Starship | Integrated Flight Test 5",
        status_name="Go for Launch",
        status_abbrev="Go",
        net_time=net,
        provider_name="SpaceX",
        provider_type="Commercial",
        rocket=RocketInfo(
            name="Starship",
            family="Starship",
            variant="Block 1",
            full_name="Starship Super Heavy",
        ),
        pad=PadInfo(
            name="Orbital Launch Mount A",
            location_name="Starbase, TX, USA",
            country_code="USA",
        ),
    )
    assert starship_launch.is_spacex is True
    assert starship_launch.is_starship is True


def test_countdown_formatting(sample_launch):
    now = sample_launch.net_time - timedelta(days=2, hours=3, minutes=15, seconds=30)
    sign, days, hours, mins, secs = sample_launch.get_countdown_tuple(now)
    assert sign == "-"
    assert days == 2
    assert hours == 3
    assert mins == 15
    assert secs == 30

    cd_str = sample_launch.format_countdown(now)
    assert cd_str == "T - 02d 03h 15m 30s"


def test_countdown_t_plus(sample_launch):
    # Test past launch (T+)
    now = sample_launch.net_time + timedelta(minutes=10, seconds=45)
    sign, days, hours, mins, secs = sample_launch.get_countdown_tuple(now)
    assert sign == "+"
    assert days == 0
    assert hours == 0
    assert mins == 10
    assert secs == 45

    cd_str = sample_launch.format_countdown(now)
    assert cd_str == "T + 00h 10m 45s"
