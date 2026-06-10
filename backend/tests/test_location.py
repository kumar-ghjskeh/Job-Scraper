"""Tests for location parsing and USA detection."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from backend.app.location_utils import parse_location


def test_santa_clara_is_usa():
    r = parse_location("Santa Clara, CA")
    assert r.is_usa is True
    assert r.state == "CA"


def test_austin_tx_is_usa():
    r = parse_location("Austin, TX")
    assert r.is_usa is True
    assert r.state == "TX"


def test_bangalore_is_not_usa():
    r = parse_location("Bangalore, India")
    assert r.is_usa is False


def test_india_explicit_not_usa():
    r = parse_location("Hyderabad, India")
    assert r.is_usa is False


def test_remote_usa_assumed():
    r = parse_location("Remote, USA")
    assert r.is_usa is True
    assert r.is_remote_usa is True


def test_remote_no_country_assumed_usa():
    r = parse_location("Remote")
    assert r.is_usa is True
    assert r.is_remote_usa is True


def test_uk_not_usa():
    r = parse_location("London, United Kingdom")
    assert r.is_usa is False


def test_canada_not_usa():
    r = parse_location("Toronto, Canada")
    assert r.is_usa is False


def test_state_abbr_detection():
    r = parse_location("San Jose, CA, United States")
    assert r.is_usa is True
    assert r.state == "CA"


def test_seattle_wa_usa():
    r = parse_location("Seattle, WA")
    assert r.is_usa is True
    assert r.state == "WA"


def test_empty_location_unknown():
    r = parse_location("")
    assert r.confidence == 0.0


def test_confidence_high_for_state_abbr():
    r = parse_location("San Diego, CA")
    assert r.confidence >= 0.85
