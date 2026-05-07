"""Holt Wetterdaten für eine Stadt und schreibt sie in die SQLite-DB.

Standalone — wird vom System-Cron stündlich aufgerufen, ohne dass der
MCP-Host laufen muss. Loggt nach /home/claude/data/cron.log.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
import db

LOG_PATH = Path("/home/claude/data/cron.log")
DEFAULT_CITY = "Kamen"
DEFAULT_COUNTRY = "DE"


def log(msg: str):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with LOG_PATH.open("a") as f:
        f.write(f"{ts}  {msg}\n")


def fetch_and_record(city: str, country: str):
    geo = httpx.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 10, "language": "de"},
        timeout=15,
    ).json()
    if not geo.get("results"):
        raise RuntimeError(f"Stadt '{city}' nicht gefunden")

    results = [r for r in geo["results"] if r.get("country_code") == country.upper()]
    if not results:
        results = geo["results"]
    loc = results[0]
    lat, lon, name = loc["latitude"], loc["longitude"], loc["name"]

    weather = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,apparent_temperature,weathercode,windspeed_10m,winddirection_10m,precipitation,relative_humidity_2m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max,weathercode,sunrise,sunset",
            "hourly": "temperature_2m,precipitation,weathercode,windspeed_10m",
            "timezone": "Europe/Berlin",
            "forecast_days": 7,
        },
        timeout=15,
    ).json()

    db.init_db()
    fetched_at = db.now_iso()
    with db.connect() as con:
        location_id = db.upsert_location(con, name, country.upper(), lat, lon)
        db.record_current(con, location_id, fetched_at, weather["current"])
        db.record_daily(con, location_id, fetched_at, weather["daily"])
        db.record_hourly(con, location_id, fetched_at, weather["hourly"])

    return name, weather["current"]


def main():
    city = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CITY
    country = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_COUNTRY
    try:
        name, current = fetch_and_record(city, country)
        log(f"OK   {name},{country}  T={current.get('temperature_2m')}°C  code={current.get('weathercode')}")
    except Exception as e:
        log(f"FAIL {city},{country}  {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
