"""Müllkalender für Kiebitzweg 12, 59174 Kamen.

Nutzt die regioit-Abfall-API (GWA Kreis Unna). Cached die Termine in SQLite
und refresht automatisch, wenn der Cache älter als 24 Stunden ist.
"""

from datetime import datetime, date, timedelta

import httpx
from mcp.server.fastmcp import FastMCP

import db
from profiling import module_load, profile

mcp = FastMCP("abfall")
db.init_db()
module_load("abfall")

API_BASE = "https://abfallapp.regioit.de/abfall-app-unna/rest"

# Hardcoded für Kiebitzweg 12, 59174 Kamen.
# Ermittelt via /orte (Kamen=1039020) → /orte/1039020/strassen (Kiebitzweg=1039291).
# Die Straße hat keine hausnummerngenaue Differenzierung (hausNrList=[]).
STREET_ID = 1039291
STREET_LABEL = "Kiebitzweg, 59174 Kamen"

# Welche Fraktionen sind für die Tonnen des Users relevant.
# Mapping fraktion_id (API) → (normalisierter Name, Anzeige-Name).
# Die API liefert auch Wertstoffcontainer, Schadstoffmobil, Weihnachtsbaum etc. —
# die filtern wir hier raus.
USER_BIN_FRAKTIONEN = {
    0: ("restmuell", "Restmüll"),
    4: ("biomuell",  "Biomüll"),
    5: ("papier",    "Papier"),
    6: ("gelb",      "Gelbe Tonne"),
}

# Wie oft wird der API-Cache aufgefrischt
CACHE_MAX_AGE_HOURS = 24


def _refresh_if_stale():
    """Holt Termine neu, falls Cache älter als CACHE_MAX_AGE_HOURS oder leer."""
    with db.connect() as con:
        latest = db.latest_abfall_fetch(con)

    if latest:
        latest_dt = datetime.fromisoformat(latest)
        age = datetime.now(latest_dt.tzinfo) - latest_dt
        if age < timedelta(hours=CACHE_MAX_AGE_HOURS):
            return  # Cache frisch genug

    _fetch_and_store()


def _fetch_and_store():
    """Lädt alle Termine für STREET_ID und schreibt sie in die DB."""
    resp = httpx.get(
        f"{API_BASE}/strassen/{STREET_ID}/termine",
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
            continue  # Wertstoffcontainer, Schadstoff, etc. überspringen
        norm, label = USER_BIN_FRAKTIONEN[fid]
        rows.append((t["datum"], fid, norm, label))

    try:
        with db.connect() as con:
            db.upsert_pickups(con, fetched_at, rows)
    except Exception as e:
        print(f"[abfall] DB-Schreiben fehlgeschlagen: {e}")


WEEKDAYS_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
               "Freitag", "Samstag", "Sonntag"]
MONTHS_DE = ["", "Januar", "Februar", "März", "April", "Mai", "Juni",
             "Juli", "August", "September", "Oktober", "November", "Dezember"]


def _format_date(d_str: str) -> str:
    d = date.fromisoformat(d_str)
    return f"{WEEKDAYS_DE[d.weekday()]}, {d.day}. {MONTHS_DE[d.month]} {d.year}"


def _today_iso() -> str:
    return date.today().isoformat()


@mcp.tool()
@profile("abfall.get_next_pickup")
def get_next_pickup() -> str:
    """Nächste anstehende Müllabfuhr für Kiebitzweg, 59174 Kamen.

    Liefert Datum, Wochentag und welche Tonne(n) abgeholt werden.
    """
    _refresh_if_stale()
    today = _today_iso()

    with db.connect() as con:
        rows = db.upcoming_pickups(
            con,
            types=[v[0] for v in USER_BIN_FRAKTIONEN.values()],
            from_date=today,
            days=14,
        )

    if not rows:
        return "Keine bevorstehenden Abholungen in den nächsten 14 Tagen gefunden."

    # Alle Einträge mit dem frühesten Datum gruppieren
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

    return (
        f"🗑️  Nächste Abholung — {STREET_LABEL}\n"
        f"{'='*50}\n"
        f"📅 {_format_date(next_date)}\n"
        f"⏱️  {when}\n"
        f"♻️  {labels}"
    )


@mcp.tool()
@profile("abfall.get_pickups")
def get_pickups(days: int = 14) -> str:
    """Alle Müllabholungen in den nächsten N Tagen für Kiebitzweg, 59174 Kamen."""
    _refresh_if_stale()
    today = _today_iso()

    with db.connect() as con:
        rows = db.upcoming_pickups(
            con,
            types=[v[0] for v in USER_BIN_FRAKTIONEN.values()],
            from_date=today,
            days=days,
        )

    if not rows:
        return f"Keine Abholungen in den nächsten {days} Tagen."

    out = f"🗑️  Müllabfuhr — {STREET_LABEL}\n"
    out += f"📅 Nächste {days} Tage\n"
    out += "=" * 50 + "\n"

    # Pro Datum gruppieren
    by_date = {}
    for d_str, _, label in rows:
        by_date.setdefault(d_str, []).append(label)

    for d_str in sorted(by_date.keys()):
        labels = ", ".join(by_date[d_str])
        out += f"{_format_date(d_str)}\n  → {labels}\n"

    return out


@mcp.tool()
@profile("abfall.get_pickups_by_type")
def get_pickups_by_type(waste_type: str) -> str:
    """Nächste Abholung einer bestimmten Tonne.

    waste_type: 'restmuell', 'biomuell', 'papier' oder 'gelb'.
    """
    valid = {v[0] for v in USER_BIN_FRAKTIONEN.values()}
    wt = waste_type.lower().strip()
    if wt not in valid:
        return (
            f"Unbekannter Tonnen-Typ '{waste_type}'. "
            f"Gültig: {', '.join(sorted(valid))}."
        )

    _refresh_if_stale()
    today = _today_iso()

    with db.connect() as con:
        row = db.next_pickup_by_type(con, wt, today)

    if not row:
        return f"Keine zukünftige Abholung für '{wt}' gefunden."

    pickup_date, label = row
    days_until = (date.fromisoformat(pickup_date) - date.today()).days
    when = "Heute" if days_until == 0 else (
        "Morgen" if days_until == 1 else f"in {days_until} Tagen"
    )
    return (
        f"♻️  {label} — nächste Abholung\n"
        f"📅 {_format_date(pickup_date)} ({when})\n"
        f"📍 {STREET_LABEL}"
    )


if __name__ == "__main__":
    mcp.run()
