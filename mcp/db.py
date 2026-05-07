"""SQLite-Persistenz für Wetterdaten.

Schreibt Current-Observations sowie Daily- und Hourly-Forecasts. Forecasts
sind durch (location_id, fetched_at, target_time) eindeutig — wiederholte
Aufrufe innerhalb derselben Sekunde überschreiben sich, ansonsten entsteht
eine Historie der Vorhersagen über die Zeit.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("/home/claude/data/weather.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS locations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    country       TEXT    NOT NULL,
    latitude      REAL    NOT NULL,
    longitude     REAL    NOT NULL,
    UNIQUE(name, country, latitude, longitude)
);

CREATE TABLE IF NOT EXISTS current_observations (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id           INTEGER NOT NULL REFERENCES locations(id),
    fetched_at            TEXT    NOT NULL,
    observed_at           TEXT    NOT NULL,
    temperature           REAL,
    apparent_temperature  REAL,
    relative_humidity     INTEGER,
    precipitation         REAL,
    windspeed             REAL,
    winddirection         REAL,
    weathercode           INTEGER
);
CREATE INDEX IF NOT EXISTS idx_current_loc_time
    ON current_observations(location_id, observed_at);

CREATE TABLE IF NOT EXISTS daily_forecasts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id       INTEGER NOT NULL REFERENCES locations(id),
    fetched_at        TEXT    NOT NULL,
    forecast_date     TEXT    NOT NULL,
    temperature_min   REAL,
    temperature_max   REAL,
    precipitation_sum REAL,
    windspeed_max     REAL,
    weathercode       INTEGER,
    sunrise           TEXT,
    sunset            TEXT,
    UNIQUE(location_id, fetched_at, forecast_date)
);
CREATE INDEX IF NOT EXISTS idx_daily_loc_date
    ON daily_forecasts(location_id, forecast_date);

CREATE TABLE IF NOT EXISTS hourly_forecasts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id   INTEGER NOT NULL REFERENCES locations(id),
    fetched_at    TEXT    NOT NULL,
    forecast_time TEXT    NOT NULL,
    temperature   REAL,
    precipitation REAL,
    weathercode   INTEGER,
    windspeed     REAL,
    UNIQUE(location_id, fetched_at, forecast_time)
);
CREATE INDEX IF NOT EXISTS idx_hourly_loc_time
    ON hourly_forecasts(location_id, forecast_time);

CREATE TABLE IF NOT EXISTS abfall_pickups (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    fetched_at       TEXT    NOT NULL,
    pickup_date      TEXT    NOT NULL,   -- YYYY-MM-DD
    fraktion_id      INTEGER NOT NULL,   -- regioit fraktion id (0,4,5,6,...)
    waste_type       TEXT    NOT NULL,   -- normalisiert: restmuell, biomuell, papier, gelb
    waste_type_label TEXT    NOT NULL,   -- API-Name: "Restmüll 2-wö.", ...
    UNIQUE(pickup_date, fraktion_id)
);
CREATE INDEX IF NOT EXISTS idx_abfall_date
    ON abfall_pickups(pickup_date);

CREATE TABLE IF NOT EXISTS mail_state (
    account       TEXT    PRIMARY KEY,   -- z.B. die Mail-Adresse
    last_seen_uid INTEGER NOT NULL,
    updated_at    TEXT    NOT NULL
);
"""


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    with connect() as con:
        con.executescript(SCHEMA)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def upsert_location(con, name: str, country: str, lat: float, lon: float) -> int:
    con.execute(
        "INSERT OR IGNORE INTO locations (name, country, latitude, longitude) "
        "VALUES (?, ?, ?, ?)",
        (name, country, lat, lon),
    )
    row = con.execute(
        "SELECT id FROM locations WHERE name = ? AND country = ? "
        "AND latitude = ? AND longitude = ?",
        (name, country, lat, lon),
    ).fetchone()
    return row[0]


def record_current(con, location_id: int, fetched_at: str, current: dict):
    con.execute(
        """INSERT INTO current_observations
           (location_id, fetched_at, observed_at, temperature, apparent_temperature,
            relative_humidity, precipitation, windspeed, winddirection, weathercode)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            location_id,
            fetched_at,
            current.get("time"),
            current.get("temperature_2m"),
            current.get("apparent_temperature"),
            current.get("relative_humidity_2m"),
            current.get("precipitation"),
            current.get("windspeed_10m"),
            current.get("winddirection_10m"),
            current.get("weathercode"),
        ),
    )


def record_daily(con, location_id: int, fetched_at: str, daily: dict):
    rows = []
    for i, day in enumerate(daily["time"]):
        rows.append((
            location_id, fetched_at, day,
            daily["temperature_2m_min"][i],
            daily["temperature_2m_max"][i],
            daily["precipitation_sum"][i],
            daily["windspeed_10m_max"][i],
            daily["weathercode"][i],
            daily["sunrise"][i],
            daily["sunset"][i],
        ))
    con.executemany(
        """INSERT OR REPLACE INTO daily_forecasts
           (location_id, fetched_at, forecast_date, temperature_min, temperature_max,
            precipitation_sum, windspeed_max, weathercode, sunrise, sunset)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )


def record_hourly(con, location_id: int, fetched_at: str, hourly: dict):
    rows = []
    for i, t in enumerate(hourly["time"]):
        rows.append((
            location_id, fetched_at, t,
            hourly["temperature_2m"][i],
            hourly["precipitation"][i],
            hourly["weathercode"][i],
            hourly["windspeed_10m"][i],
        ))
    con.executemany(
        """INSERT OR REPLACE INTO hourly_forecasts
           (location_id, fetched_at, forecast_time, temperature, precipitation,
            weathercode, windspeed)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )


def find_location(con, name: str, country: str):
    return con.execute(
        "SELECT id, name, country FROM locations "
        "WHERE LOWER(name) = LOWER(?) AND UPPER(country) = UPPER(?) "
        "ORDER BY id LIMIT 1",
        (name, country),
    ).fetchone()


def recent_observations(con, location_id: int, hours: int):
    return con.execute(
        """SELECT observed_at, temperature, precipitation, windspeed, weathercode
           FROM current_observations
           WHERE location_id = ?
             AND observed_at >= datetime('now', ?)
           ORDER BY observed_at DESC""",
        (location_id, f"-{hours} hours"),
    ).fetchall()


def daily_forecast_drift(con, location_id: int, forecast_date: str):
    return con.execute(
        """SELECT fetched_at, temperature_min, temperature_max,
                  precipitation_sum, windspeed_max, weathercode
           FROM daily_forecasts
           WHERE location_id = ? AND forecast_date = ?
           ORDER BY fetched_at""",
        (location_id, forecast_date),
    ).fetchall()


def hourly_forecast_drift(con, location_id: int, forecast_time: str):
    return con.execute(
        """SELECT fetched_at, temperature, precipitation, windspeed, weathercode
           FROM hourly_forecasts
           WHERE location_id = ? AND forecast_time = ?
           ORDER BY fetched_at""",
        (location_id, forecast_time),
    ).fetchall()


def upsert_pickups(con, fetched_at: str, pickups: list[tuple]):
    """pickups: Liste von (pickup_date, fraktion_id, waste_type, waste_type_label)."""
    rows = [(fetched_at, *p) for p in pickups]
    con.executemany(
        """INSERT OR REPLACE INTO abfall_pickups
           (fetched_at, pickup_date, fraktion_id, waste_type, waste_type_label)
           VALUES (?, ?, ?, ?, ?)""",
        rows,
    )


def latest_abfall_fetch(con) -> str | None:
    row = con.execute(
        "SELECT MAX(fetched_at) FROM abfall_pickups"
    ).fetchone()
    return row[0] if row and row[0] else None


def upcoming_pickups(con, types: list[str], from_date: str, days: int):
    placeholders = ",".join("?" * len(types))
    return con.execute(
        f"""SELECT pickup_date, waste_type, waste_type_label
            FROM abfall_pickups
            WHERE waste_type IN ({placeholders})
              AND pickup_date >= ?
              AND pickup_date < DATE(?, ?)
            ORDER BY pickup_date, waste_type""",
        (*types, from_date, from_date, f"+{days} days"),
    ).fetchall()


def next_pickup_by_type(con, waste_type: str, from_date: str):
    return con.execute(
        """SELECT pickup_date, waste_type_label
           FROM abfall_pickups
           WHERE waste_type = ? AND pickup_date >= ?
           ORDER BY pickup_date LIMIT 1""",
        (waste_type, from_date),
    ).fetchone()


def get_last_seen_uid(con, account: str) -> int | None:
    row = con.execute(
        "SELECT last_seen_uid FROM mail_state WHERE account = ?",
        (account,),
    ).fetchone()
    return row[0] if row else None


def set_last_seen_uid(con, account: str, uid: int):
    con.execute(
        """INSERT INTO mail_state (account, last_seen_uid, updated_at)
           VALUES (?, ?, ?)
           ON CONFLICT(account) DO UPDATE SET
               last_seen_uid = excluded.last_seen_uid,
               updated_at    = excluded.updated_at""",
        (account, uid, now_iso()),
    )


def daily_aggregates(con, location_id: int, days: int):
    """Min/Max/Avg über alle 'current'-Beobachtungen pro Tag."""
    return con.execute(
        """SELECT DATE(observed_at) AS day,
                  MIN(temperature) AS t_min,
                  MAX(temperature) AS t_max,
                  ROUND(AVG(temperature), 1) AS t_avg,
                  ROUND(SUM(precipitation), 1) AS rain_sum,
                  COUNT(*) AS samples
           FROM current_observations
           WHERE location_id = ?
             AND observed_at >= DATE('now', ?)
           GROUP BY day
           ORDER BY day DESC""",
        (location_id, f"-{days} days"),
    ).fetchall()
