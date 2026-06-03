import httpx
from datetime import datetime, timedelta, timezone
from mcp.server.fastmcp import FastMCP

import db
from profiling import module_load, profile

mcp = FastMCP("weather")
db.init_db()
module_load("weather")

WEATHER_CACHE_MAX_AGE_MINUTES = 30

WMO = {
    0: "Klar", 1: "Überwiegend klar", 2: "Teilweise bewölkt", 3: "Bedeckt",
    45: "Nebel", 48: "Raureif",
    51: "Leichter Nieselregen", 53: "Nieselregen", 55: "Starker Nieselregen",
    61: "Leichter Regen", 63: "Regen", 65: "Starker Regen",
    71: "Leichter Schnee", 73: "Schnee", 75: "Starker Schnee",
    80: "Leichte Schauer", 81: "Schauer", 82: "Starke Schauer",
    95: "Gewitter", 96: "Gewitter mit Hagel", 99: "Starkes Gewitter",
}


def wcode(code):
    return WMO.get(code, f"Code {code}")

def _cache_age_minutes(cached_at: str) -> float:
    """Berechnet Alter einer Timestamp-String (ISO 8601) in Minuten."""
    cached_dt = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
    now_dt = datetime.now(timezone.utc)
    return (now_dt - cached_dt).total_seconds() / 60


def get_weather_impl(
    city: str,
    country: str = "DE",
    include_hourly: bool = False,
    *,
    http_get=None,
    db_connect=None,
) -> str:
    """Aktuelles Wetter + 3 und 7 Tage Vorhersage für eine Stadt. Mit include_hourly=True zusätzlich stündliche Vorhersage für heute."""
    http_get = http_get or httpx.get
    db_connect = db_connect or db.connect

    # Schritt 0: Geocoding-Cache + Response-Cache prüfen
    with db_connect() as con:
        loc = db.find_location(con, city, country)
        if loc:
            location_id, loc_name, loc_country, lat, lon = loc
            # Response-Cache prüfen
            cached = db.get_weather_cache(con, location_id, include_hourly)
            if cached:
                cached_at, response_text = cached
                age = _cache_age_minutes(cached_at)
                if age < WEATHER_CACHE_MAX_AGE_MINUTES:
                    return response_text

    # Schritt 1: Stadt -> Koordinaten (falls nicht in Cache)
    geo = http_get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 10, "language": "de"}
    ).json()

    if not geo.get("results"):
        return f"Stadt '{city}' nicht gefunden."

    # Passendes Land filtern
    results = [r for r in geo["results"] if r.get("country_code") == country.upper()]
    if not results:
        results = geo["results"]  # Fallback: erstes Ergebnis

    loc = results[0]
    lat, lon = loc["latitude"], loc["longitude"]
    name = loc["name"]
    country_name = loc.get("country", "")

    # Schritt 2: Koordinaten -> Wetter
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,apparent_temperature,weathercode,windspeed_10m,winddirection_10m,precipitation,relative_humidity_2m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max,weathercode,sunrise,sunset",
        "timezone": "Europe/Berlin",
        "forecast_days": 7
    }
    if include_hourly:
        params["hourly"] = "temperature_2m,precipitation,weathercode,windspeed_10m"

    weather = http_get("https://api.open-meteo.com/v1/forecast", params=params).json()

    c = weather["current"]
    d = weather["daily"]

    # Persistieren — DB-Fehler dürfen den Tool-Aufruf nicht brechen
    try:
        fetched_at = db.now_iso()
        with db_connect() as con:
            location_id = db.upsert_location(con, name, country.upper(), lat, lon)
            db.record_current(con, location_id, fetched_at, c)
            db.record_daily(con, location_id, fetched_at, d)
            if include_hourly and "hourly" in weather:
                db.record_hourly(con, location_id, fetched_at, weather["hourly"])
    except Exception as e:
        print(f"[weather] DB-Schreiben fehlgeschlagen: {e}")

    result = f"""
📍 Aktuelles Wetter in {name}, {country_name}
{'='*40}
🌡️  Temperatur:       {c['temperature_2m']}°C (gefühlt {c['apparent_temperature']}°C)
💧 Luftfeuchtigkeit: {c['relative_humidity_2m']}%
🌧️  Niederschlag:     {c['precipitation']} mm
💨 Wind:             {c['windspeed_10m']} km/h
☁️  Wetter:           {wcode(c['weathercode'])}

📅 3-Tage Vorhersage
{'='*40}
"""
    for i in range(3):
        result += f"{d['time'][i]}:  {d['temperature_2m_min'][i]}°C – {d['temperature_2m_max'][i]}°C  |  {wcode(d['weathercode'][i])}  |  🌧️ {d['precipitation_sum'][i]} mm  |  💨 {d['windspeed_10m_max'][i]} km/h\n"

    result += f"""
📅 7-Tage Vorhersage
{'='*40}
"""
    for i in range(7):
        result += f"{d['time'][i]}:  {d['temperature_2m_min'][i]}°C – {d['temperature_2m_max'][i]}°C  |  {wcode(d['weathercode'][i])}  |  🌧️ {d['precipitation_sum'][i]} mm\n"

    if include_hourly:
        h = weather["hourly"]
        today = d["time"][0]
        result += f"""
🕐 Stündlich heute ({today})
{'='*40}
"""
        for i, t in enumerate(h["time"]):
            if not t.startswith(today):
                continue
            hour = t.split("T")[1]
            result += f"{hour}:  {h['temperature_2m'][i]}°C  |  {wcode(h['weathercode'][i])}  |  🌧️ {h['precipitation'][i]} mm  |  💨 {h['windspeed_10m'][i]} km/h\n"

    # Cache schreiben
    try:
        with db_connect() as con:
            db.set_weather_cache(con, location_id, include_hourly, result)
    except Exception as e:
        print(f"[weather] Cache-Schreiben fehlgeschlagen: {e}")

    return result


@mcp.tool()
@profile("weather.get_weather")
def get_weather(city: str, country: str = "DE", include_hourly: bool = False) -> str:
    """Aktuelles Wetter + 3 und 7 Tage Vorhersage für eine Stadt. Mit include_hourly=True zusätzlich stündliche Vorhersage für heute."""
    return get_weather_impl(city, country, include_hourly)

@mcp.tool()
@profile("weather.get_forecast_history")
def get_forecast_history(city: str, date: str, country: str = "DE", hour: int | None = None) -> str:
    """Zeigt, wie sich die Vorhersage für ein bestimmtes Datum über die Zeit verändert hat.

    date: YYYY-MM-DD. Ohne hour: Daily-Verlauf (Min/Max/Regen pro Fetch).
    Mit hour (0-23): Hourly-Verlauf für diese Stunde des Tages.
    """
    with db.connect() as con:
        loc = db.find_location(con, city, country)
        if not loc:
            return f"Keine Daten für '{city}, {country}' in der DB."
        loc_id, loc_name, loc_country = loc

        if hour is None:
            rows = db.daily_forecast_drift(con, loc_id, date)
        else:
            forecast_time = f"{date}T{hour:02d}:00"
            rows = db.hourly_forecast_drift(con, loc_id, forecast_time)

    if not rows:
        target = date if hour is None else f"{date} {hour:02d}:00"
        return f"Keine Vorhersage-Historie für {target} in {loc_name}, {loc_country}."

    target = date if hour is None else f"{date} um {hour:02d}:00 Uhr"
    out = f"\n📈 Vorhersage-Verlauf {loc_name}, {loc_country} — {target}\n"
    out += "=" * 75 + "\n"

    if hour is None:
        out += f"{'fetched_at':<22} {'min':>7} {'max':>7} {'Regen':>9} {'Wind':>9} {'Wetter':<22}\n"
        out += "-" * 75 + "\n"
        for fetched_at, t_min, t_max, rain, wind, code in rows:
            out += f"{fetched_at:<22} {t_min:>5}°C {t_max:>5}°C {rain:>6} mm {wind:>6} km/h {wcode(code):<22}\n"
    else:
        out += f"{'fetched_at':<22} {'T':>7} {'Regen':>9} {'Wind':>9} {'Wetter':<22}\n"
        out += "-" * 75 + "\n"
        for fetched_at, temp, rain, wind, code in rows:
            out += f"{fetched_at:<22} {temp:>5}°C {rain:>6} mm {wind:>6} km/h {wcode(code):<22}\n"

    out += f"\n{len(rows)} Fetches gefunden."
    return out


@mcp.tool()
@profile("weather.get_weather_history")
def get_weather_history(city: str, country: str = "DE", days: int = 7) -> str:
    """Historische Wetterdaten aus der lokalen DB für eine Stadt. Gibt Tagesaggregate (Min/Max/Ø Temp, Regensumme) der letzten N Tage zurück."""
    with db.connect() as con:
        loc = db.find_location(con, city, country)
        if not loc:
            return f"Keine Daten für '{city}, {country}' in der DB. Erst `get_weather` aufrufen."

        loc_id, loc_name, loc_country = loc
        rows = db.daily_aggregates(con, loc_id, days)

    if not rows:
        return f"Keine Beobachtungen in den letzten {days} Tagen für {loc_name}, {loc_country}."

    out = f"\n📊 Wetterhistorie {loc_name}, {loc_country} (letzte {days} Tage)\n"
    out += "=" * 60 + "\n"
    out += f"{'Tag':<12} {'Min':>6} {'Max':>6} {'Ø':>6} {'Regen':>8} {'Samples':>8}\n"
    out += "-" * 60 + "\n"
    for day, t_min, t_max, t_avg, rain_sum, samples in rows:
        out += f"{day:<12} {t_min:>5}°C {t_max:>5}°C {t_avg:>5}°C {rain_sum:>6} mm {samples:>8}\n"
    return out


if __name__ == "__main__":
    mcp.run()
