"""Unit tests for tracker CLI argument parsing."""

from space_suite.iss.tracker import parse_args


def test_parse_args_defaults():
    args = parse_args([])
    assert args.lat == 51.5074
    assert args.lon == -0.1278
    assert args.web is False
    assert args.simulate_pass is False
    assert args.test_notify is False
    assert args.port == 8055


def test_parse_args_web_flag():
    args = parse_args(["--web", "--port", "9000"])
    assert args.web is True
    assert args.port == 9000


def test_parse_args_simulate_pass():
    args = parse_args(["--simulate-pass"])
    assert args.simulate_pass is True


def test_parse_args_custom_coords():
    args = parse_args(["--lat", "40.7128", "--lon", "-74.0060", "--name", "New York"])
    assert args.lat == 40.7128
    assert args.lon == -74.0060
    assert args.name == "New York"
