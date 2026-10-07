"""Unit tests for notification dispatching and debouncing."""

from unittest.mock import patch

import pytest

from space_suite.iss.models import ISSTelemetry, ObserverCoords, RelativePosition
from space_suite.iss.notifier import UbuntuNotifier


@pytest.fixture
def dummy_telemetry():
    return ISSTelemetry(
        name="iss",
        id=25544,
        latitude=51.5,
        longitude=-0.1,
        altitude_km=420.0,
        velocity_kmh=27600.0,
        visibility="daylight",
        footprint_km=4500.0,
        timestamp=1700000000.0,
    )


@pytest.fixture
def dummy_observer():
    return ObserverCoords(latitude=51.5, longitude=-0.1, name="Test Station")


def test_notifier_debounce(dummy_telemetry, dummy_observer):
    notifier = UbuntuNotifier(app_name="TestNotifier", cooldown_seconds=600.0)
    notifier._notify_bin = "/usr/bin/notify-send"

    with patch.object(notifier, "send_notification", return_value=True) as mock_send:
        # Step 1: Out of range
        rel_out = RelativePosition(
            ground_distance_km=2500.0,
            slant_range_km=2550.0,
            elevation_deg=-15.0,
            bearing_deg=180.0,
            compass_heading="S",
            is_above_horizon=False,
            is_in_range=False,
        )
        assert notifier.evaluate_and_notify(rel_out, dummy_telemetry, dummy_observer) is False
        mock_send.assert_not_called()

        # Step 2: Enters range -> Should trigger notification
        rel_in = RelativePosition(
            ground_distance_km=450.0,
            slant_range_km=600.0,
            elevation_deg=45.0,
            bearing_deg=180.0,
            compass_heading="S",
            is_above_horizon=True,
            is_in_range=True,
        )
        assert notifier.evaluate_and_notify(rel_in, dummy_telemetry, dummy_observer) is True
        assert mock_send.call_count == 1

        # Step 3: Still in range on next poll -> Should NOT trigger duplicate notification
        assert notifier.evaluate_and_notify(rel_in, dummy_telemetry, dummy_observer) is False
        assert mock_send.call_count == 1

        # Step 4: Leaves range -> Resets state
        assert notifier.evaluate_and_notify(rel_out, dummy_telemetry, dummy_observer) is False
        assert mock_send.call_count == 1
