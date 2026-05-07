"""Mail-Polling-MCP für Briefing-/Notification-Workflows.

Liefert nur **neue** E-Mails seit der letzten Prüfung (UID-basiert) und
persistiert den Stand in der gemeinsamen SQLite-DB. Liest dieselben
Credentials wie `gmx_mail.py` aus den Env-Vars `GMX_EMAIL` / `GMX_PASSWORD`.

Beim allerersten Aufruf wird kein Backlog reportet — der aktuelle höchste
UID wird als Baseline gesetzt, sodass nur danach eintreffende Mails als
"neu" gelten. So vermeidet man Spam beim Erstlauf.
"""

import imaplib
import email
import os
from email.header import decode_header

from mcp.server.fastmcp import FastMCP

import db
from profiling import module_load, profile

mcp = FastMCP("mail_check")
module_load("mail_check")

IMAP_HOST = "imap.gmx.net"
IMAP_PORT = 993
EMAIL    = os.environ["GMX_EMAIL"]
PASSWORD = os.environ["GMX_PASSWORD"]

db.init_db()


def _decode(value):
    if value is None:
        return ""
    out = ""
    for part, enc in decode_header(value):
        if isinstance(part, bytes):
            out += part.decode(enc or "utf-8", errors="replace")
        else:
            out += part
    return out


def _fetch_uids_since(mail, since_uid: int | None) -> list[int]:
    """Liefert sortierte UID-Liste. Ohne since_uid: alle UIDs."""
    criterion = "ALL" if since_uid is None else f"UID {since_uid + 1}:*"
    typ, data = mail.uid("search", None, criterion)
    if typ != "OK" or not data or not data[0]:
        return []
    uids = [int(x) for x in data[0].split()]
    # IMAP "UID N:*" liefert auch UID N selbst zurück, falls keine größeren
    # existieren — defensive Filterung:
    if since_uid is not None:
        uids = [u for u in uids if u > since_uid]
    return sorted(uids)


@mcp.tool()
@profile("mail_check.get_new_emails")
def get_new_emails(max_report: int = 10) -> str:
    """Neue E-Mails seit letzter Prüfung.

    Beim Erstlauf wird nur die Baseline gesetzt (gibt 'Baseline gesetzt' zurück).
    Danach werden alle seither eingetroffenen Mails kompakt aufgelistet und der
    Stand wird gespeichert. Maximal `max_report` Einträge im Output, der Counter
    bleibt aber korrekt.
    """
    with db.connect() as con:
        last_uid = db.get_last_seen_uid(con, EMAIL)

    mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    try:
        mail.login(EMAIL, PASSWORD)
        mail.select("INBOX", readonly=True)

        new_uids = _fetch_uids_since(mail, last_uid)

        if last_uid is None:
            # Erstlauf: Baseline auf höchste UID setzen, nichts reporten.
            baseline = max(new_uids) if new_uids else 0
            with db.connect() as con:
                db.set_last_seen_uid(con, EMAIL, baseline)
            return f"📬 Baseline gesetzt (UID {baseline}). Ab jetzt werden neue Mails gemeldet."

        if not new_uids:
            return "📬 Keine neuen E-Mails."

        report_uids = new_uids[-max_report:]
        lines = [f"📬 {len(new_uids)} neue E-Mail{'s' if len(new_uids) != 1 else ''}"]
        if len(new_uids) > max_report:
            lines.append(f"(zeige neueste {max_report})")
        lines.append("─" * 40)

        for uid in reversed(report_uids):
            typ, data = mail.uid("fetch", str(uid), "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if typ != "OK" or not data or not data[0]:
                continue
            msg = email.message_from_bytes(data[0][1])
            sender = _decode(msg["From"])
            subject = _decode(msg["Subject"]) or "(kein Betreff)"
            lines.append(f"📧 {sender}")
            lines.append(f"   {subject}")

        with db.connect() as con:
            db.set_last_seen_uid(con, EMAIL, max(new_uids))

        return "\n".join(lines)
    finally:
        try:
            mail.logout()
        except Exception:
            pass


@mcp.tool()
@profile("mail_check.reset_mail_baseline")
def reset_mail_baseline() -> str:
    """Setzt die Baseline neu — nächster `get_new_emails`-Aufruf reportet erneut Erstlauf."""
    with db.connect() as con:
        con.execute("DELETE FROM mail_state WHERE account = ?", (EMAIL,))
    return f"📬 Baseline für {EMAIL} zurückgesetzt."


if __name__ == "__main__":
    mcp.run()
