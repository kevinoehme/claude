"""Müllkalender für Kamen (PLZ 59174).

Nutzt die regioit-Abfall-API (GWA Kreis Unna). Cached die Termine in SQLite
und refresht automatisch, wenn der Cache älter als 24 Stunden ist.

Standort-spezifische Werte (Straße, street_id) werden aus
/home/claude/data/location.json geladen — Template: mcp/location.json.example.
"""

import json
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

import db
from profiling import module_load, profile

mcp = FastMCP("abfall")
db.init_db()
module_load("abfall")

API_BASE = "https://abfallapp.regioit.de/abfall-app-unna/rest"

LOCATION_CONFIG_PATH = Path("/home/claude/data/location.json")

USER_BIN_FRAKTIONEN = {
    0: ("restmuell", "Restmüll"),
    4: ("biomuell",  "Biomüll"),
    5: ("papier",    "Papier"),
    6: ("gelb",      "Gelbe Tonne"),
}

CACHE_MAX_AGE_HOURS = 24

WEEKDAYS_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
               "Freitag", "Samstag", "Sonntag"]
MONTHS_DE = ["", "Januar", "Februar", "März", "April", "Mai", "Juni",
             "Juli", "August", "September", "Oktober", "November", "Dezember"]


def _load_location():
    if not LOCATION_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Standort-Config fehlt: {LOCATION_CONFIG_PATH}. "
            "Kopiere /home/claude/mcp/location.json.example dorthin und passe die Werte an."
        )
    with LOCATION_CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _format_date(d_str: str) -> str:
    d = date.fromisoformat(d_str)
    return f"{WEEKDAYS_DE[d.weekday()]}, {d.day}. {MONTHS_DE[d.month]} {d.year}"


def _today_iso() -> str:
    return date.today().isoformat()


def _refresh_if_stale_impl(db_connect, http_get, location_cfg):
    """Holt Termine neu, falls Cache älter als CACHE_MAX_AGE_HOURS oder leer."""
    with db_connect() as con:
        latest = db.latest_abfall_fetch(con)

    if latest:
        latest_dt = datetime.fromisoformat(latest)
        age = datetime.now(latest_dt.tzinfo) - latest_dt
        if age < timedelta(hours=CACHE_MAX_AGE_HOURS):
            return

    _fetch_and_store_impl(db_connect, http_get, location_cfg)


def _fetch_and_store_impl(db_connect, http_get, location_cfg):
    """Lädt alle Termine für street_id und schreibt sie in die DB."""
    street_id = location_cfg["abfall"]["street_id"]
    resp = http_get(
        f"{API_BASE}/strassen/{street_id}/termine",
        headers={"Accept": "application/json"},
        timeout=15.0,
    )
    resp.raise_for_status()
    termine = resp.json()

    fetched_at = db.now_iso()
    rows = []
    for t in termine:
        fid = t["bezirk"]["fraktionId"]
        if fid not in USER_BIN_FRAKTIONEN:
            continue
        norm, label = USER_BIN_FRAKTIONEN[fid]
        rows.append((t["datum"], fid, norm, label))

    try:
        with db_connect() as con:
            db.upsert_pickups(con, fetched_at, rows)
    except Exception as e:
        print(f"[abfall] DB-Schreiben fehlgeschlagen: {e}")


def get_next_pickup_impl(
    *, http_get=None, db_connect=None, location_cfg=None
) -> str:
    """Nächste anstehende Müllabfuhr für den in location.json konfigurierten Standort."""
    http_get = http_get or httpx.get
    db_connect = db_connect or db.connect
    location_cfg = location_cfg or _load_location()

    _refresh_if_stale_impl(db_connect, http_get, location_cfg)
    today = _today_iso()

    with db_connect() as con:
        rows = db.upcoming_pickups(
            con,
            types=[v[0] for v in USER_BIN_FRAKTIONEN.values()],
            from_date=today,
            days=14,
        )

    if not rows:
        return "Keine bevorstehenden Abholungen in den nächsten 14 Tagen gefunden."

    next_date = rows[0][0]
    same_day = [r for r in rows if r[0] == next_date]
    labels = ", ".join(r[2] for r in same_day)

    days_until = (date.fromisoformat(next_date) - date.today()).days
    if days_until == 0:
        when = "Heute"
    elif days_until == 1:
        when = "Morgen"
    else:
        when = f"In {days_until} Tagen"

    street_label = location_cfg["abfall"]["street_label"]
    return (
        f"🗑️  Nächste Abholung — {street_label}\n"
        f"{'='*50}\n"
        f"📅 {_format_date(next_date)}\n"
        f"⏱️  {when}\n"
        f"♻️  {labels}"
    )


def get_pickups_impl(days: int = 14, *, http_get=None, db_connect=None, location_cfg=None) -> str:
    """Alle Müllabholungen in den nächsten N Tagen für den in location.json konfigurierten Standort."""
    http_get = http_get or httpx.get
    db_connect = db_connect or db.connect
    location_cfg = location_cfg or _load_location()

    _refresh_if_stale_impl(db_connect, http_get, location_cfg)
    today = _today_iso()

    with db_connect() as con:
        rows = db.upcoming_pickups(
            con,
            types=[v[0] for v in USER_BIN_FRAKTIONEN.values()],
            from_date=today,
            days=days,
        )

    if not rows:
        return f"Keine Abholungen in den nächsten {days} Tagen."

    street_label = location_cfg["abfall"]["street_label"]
    out = f"🗑️  Müllabfuhr — {street_label}\n"
    out += f"📅 Nächste {days} Tage\n"
    out += "=" * 50 + "\n"

    by_date = {}
    for d_str, _, label in rows:
        by_date.setdefault(d_str, []).append(label)

    for d_str in sorted(by_date.keys()):
        labels = ", ".join(by_date[d_str])
        out += f"{_format_date(d_str)}\n  → {labels}\n"

    return out


def get_pickups_by_type_impl(waste_type: str, *, http_get=None, db_connect=None, location_cfg=None) -> str:
    """Nächste Abholung einer bestimmten Tonne."""
    http_get = http_get or httpx.get
    db_connect = db_connect or db.connect
    location_cfg = location_cfg or _load_location()

    valid = {v[0] for v in USER_BIN_FRAKTIONEN.values()}
    wt = waste_type.lower().strip()
    if wt not in valid:
        return (
            f"Unbekannter Tonnen-Typ '{waste_type}'. "
            f"Gültig: {', '.join(sorted(valid))}."
        )

    _refresh_if_stale_impl(db_connect, http_get, location_cfg)
    today = _today_iso()

    with db_connect() as con:
        row = db.next_pickup_by_type(con, wt, today)

    if not row:
        return f"Keine zukünftige Abholung für '{wt}' gefunden."

    pickup_date, label = row
    days_until = (date.fromisoformat(pickup_date) - date.today()).days
    when = "Heute" if days_until == 0 else (
        "Morgen" if days_until == 1 else f"in {days_until} Tagen"
    )
    street_label = location_cfg["abfall"]["street_label"]
    return (
        f"♻️  {label} — nächste Abholung\n"
        f"📅 {_format_date(pickup_date)} ({when})\n"
        f"📍 {street_label}"
    )


@mcp.tool()
@profile("abfall.get_next_pickup")
def get_next_pickup() -> str:
    """Nächste anstehende Müllabfuhr für den in location.json konfigurierten Standort."""
    return get_next_pickup_impl()


@mcp.tool()
@profile("abfall.get_pickups")
def get_pickups(days: int = 14) -> str:
    """Alle Müllabholungen in den nächsten N Tagen für den in location.json konfigurierten Standort."""
    return get_pickups_impl(days)


@mcp.tool()
@profile("abfall.get_pickups_by_type")
def get_pickups_by_type(waste_type: str) -> str:
    """Nächste Abholung einer bestimmten Tonne."""
    return get_pickups_by_type_impl(waste_type)


if __name__ == "__main__":
    if "--test" in sys.argv:
        print("[test] get_next_pickup():")
        print(get_next_pickup_impl())
    else:
        mcp.run()
