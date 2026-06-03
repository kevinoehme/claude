"""Tests für weather.py — TTL-Cache + DI."""
import sys
from pathlib import Path
from datetime import datetime, timezone

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import weather
import db


def test_weather_cache_hit(tmp_db, mocker):
    """Response-Cache-Hit: http_get wird nicht aufgerufen."""
    mock_http_get = mocker.MagicMock()

    # Populate cache manually
    with tmp_db() as con:
        loc_id = db.upsert_location(con, "Kamen", "DE", 51.5, 7.5)
        cached_text = "📍 Aktuelles Wetter in Kamen, Germany\n..."
        db.set_weather_cache(con, loc_id, False, cached_text)

    # Call with mocked http_get
    result = weather.get_weather_impl(
        "Kamen",
        include_hourly=False,
        http_get=mock_http_get,
        db_connect=tmp_db,
    )

    assert result == cached_text
    assert mock_http_get.call_count == 0  # No HTTP calls


def test_weather_cache_miss(tmp_db, mocker):
    """Cache-Miss: http_get wird aufgerufen."""
    mock_http_get = mocker.MagicMock()
    mock_geo = {
        "results": [
            {
                "name": "Kamen",
                "country": "Germany",
                "country_code": "DE",
                "latitude": 51.5,
                "longitude": 7.5,
            }
        ]
    }
    mock_weather = {
        "current": {
            "temperature_2m": 15,
            "apparent_temperature": 14,
            "relative_humidity_2m": 60,
            "precipitation": 0,
            "windspeed_10m": 5,
            "winddirection_10m": 180,
            "weathercode": 1,
            "time": "2026-06-03T12:00",
        },
        "daily": {
            "time": ["2026-06-03", "2026-06-04", "2026-06-05", "2026-06-06", "2026-06-07"],
            "temperature_2m_min": [10, 11, 12, 13, 14],
            "temperature_2m_max": [18, 19, 20, 21, 22],
            "precipitation_sum": [0, 0.5, 1, 0.2, 0],
            "windspeed_10m_max": [10, 12, 8, 15, 6],
            "weathercode": [1, 61, 1, 80, 0],
            "sunrise": ["06:00", "06:00", "06:00", "06:00", "06:00"],
            "sunset": ["21:30", "21:31", "21:32", "21:33", "21:34"],
        },
    }

    mock_http_get.side_effect = [
        mocker.MagicMock(json=mocker.MagicMock(return_value=mock_geo)),
        mocker.MagicMock(json=mocker.MagicMock(return_value=mock_weather)),
    ]

    result = weather.get_weather_impl(
        "Kamen",
        include_hourly=False,
        http_get=mock_http_get,
        db_connect=tmp_db,
    )

    assert "15°C" in result  # Current temp
    assert "Kamen" in result
    assert mock_http_get.call_count == 2  # Geocoding + forecast


def test_weather_stale_cache_refresh(tmp_db, mocker):
    """Stale Cache (>30 min): fetch läuft, Cache aktualisiert."""
    mock_http_get = mocker.MagicMock()
    mock_geo = {
        "results": [
            {
                "name": "Kamen",
                "country": "Germany",
                "country_code": "DE",
                "latitude": 51.5,
                "longitude": 7.5,
            }
        ]
    }
    mock_weather = {
        "current": {
            "temperature_2m": 20,
            "apparent_temperature": 19,
            "relative_humidity_2m": 70,
            "precipitation": 0.5,
            "windspeed_10m": 8,
            "winddirection_10m": 200,
            "weathercode": 61,
            "time": "2026-06-03T14:00",
        },
        "daily": {
            "time": ["2026-06-03", "2026-06-04", "2026-06-05", "2026-06-06", "2026-06-07"],
            "temperature_2m_min": [10, 11, 12, 13, 14],
            "temperature_2m_max": [18, 19, 20, 21, 22],
            "precipitation_sum": [1, 0.5, 0.2, 0, 0],
            "windspeed_10m_max": [10, 12, 8, 6, 5],
            "weathercode": [61, 61, 1, 1, 0],
            "sunrise": ["06:00"] * 5,
            "sunset": ["21:30", "21:31", "21:32", "21:33", "21:34"],
        },
    }

    mock_http_get.side_effect = [
        mocker.MagicMock(json=mocker.MagicMock(return_value=mock_geo)),
        mocker.MagicMock(json=mocker.MagicMock(return_value=mock_weather)),
    ]

    # Pre-populate stale cache
    with tmp_db() as con:
        loc_id = db.upsert_location(con, "Kamen", "DE", 51.5, 7.5)
        old_text = "Old cached text"
        db.set_weather_cache(con, loc_id, False, old_text)
        # Manually set old timestamp
        con.execute(
            "UPDATE weather_cache SET cached_at = ? WHERE location_id = ?",
            ("2026-06-03T00:00:00+00:00", loc_id),
        )

    result = weather.get_weather_impl(
        "Kamen",
        include_hourly=False,
        http_get=mock_http_get,
        db_connect=tmp_db,
    )

    assert result != old_text
    assert "20°C" in result  # New temp
    assert mock_http_get.call_count == 2  # Fetch ran
