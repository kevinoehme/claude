"""Tests für abfall.py — TTL-Cache + DI."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import abfall
import db


def test_abfall_fresh_cache_no_http(tmp_db, mocker):
    """Frischer Cache (<24h): kein HTTP-Call."""
    mock_http_get = mocker.MagicMock()
    location_cfg = {"abfall": {"street_id": "test_street", "street_label": "Teststraße"}}

    # Populate fresh cache
    with tmp_db() as con:
        fetched_at = db.now_iso()
        pickups = [("2026-06-05", 0, "restmuell", "Restmüll")]
        db.upsert_pickups(con, fetched_at, pickups)

    result = abfall.get_next_pickup_impl(
        http_get=mock_http_get,
        db_connect=tmp_db,
        location_cfg=location_cfg,
    )

    assert "Teststraße" in result
    assert "rest" in result.lower()
    assert mock_http_get.call_count == 0  # No HTTP


def test_abfall_stale_cache_refresh(tmp_db, mocker):
    """Staler Cache (>24h): HTTP-Call."""
    mock_http_get = mocker.MagicMock()
    mock_api_response = [
        {
            "datum": "2026-06-10",
            "bezirk": {"fraktionId": 0},  # Restmüll
        },
        {
            "datum": "2026-06-12",
            "bezirk": {"fraktionId": 4},  # Biomüll
        },
    ]
    mock_http_get.return_value.json.return_value = mock_api_response

    location_cfg = {"abfall": {"street_id": "test_street", "street_label": "Teststraße"}}

    # Pre-populate stale cache
    with tmp_db() as con:
        con.execute(
            "INSERT INTO abfall_pickups "
            "(fetched_at, pickup_date, fraktion_id, waste_type, waste_type_label) "
            "VALUES (?, ?, ?, ?, ?)",
            ("2026-05-30T00:00:00+00:00", "2026-05-31", 0, "restmuell", "Restmüll"),
        )

    result = abfall.get_next_pickup_impl(
        http_get=mock_http_get,
        db_connect=tmp_db,
        location_cfg=location_cfg,
    )

    assert mock_http_get.call_count == 1  # Fetch ran
    assert "2026-06-10" in result or "10" in result  # New date


def test_abfall_get_next_pickup_format(tmp_db):
    """Format der get_next_pickup()-Antwort."""
    location_cfg = {"abfall": {"street_id": "test_street", "street_label": "Teststraße"}}

    with tmp_db() as con:
        fetched_at = db.now_iso()
        pickups = [("2026-06-05", 0, "restmuell", "Restmüll")]
        db.upsert_pickups(con, fetched_at, pickups)

    result = abfall.get_next_pickup_impl(
        http_get=lambda *a, **k: None,
        db_connect=tmp_db,
        location_cfg=location_cfg,
    )

    assert "🗑️" in result
    assert "Abholung" in result
    assert "Teststraße" in result
