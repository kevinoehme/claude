import imaplib
import email
import os
from email.header import decode_header
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("email")

IMAP_HOST = "imap.gmx.net"
IMAP_PORT = 993
EMAIL    = os.environ["GMX_EMAIL"]
PASSWORD = os.environ["GMX_PASSWORD"]

def decode_str(value):
    if value is None:
        return ""
    parts = decode_header(value)
    result = ""
    for part, enc in parts:
        if isinstance(part, bytes):
            result += part.decode(enc or "utf-8", errors="replace")
        else:
            result += part
    return result

@mcp.tool()
def get_emails(count: int = 10) -> str:
    """Letzte E-Mails aus dem GMX Posteingang abrufen"""
    mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    mail.login(EMAIL, PASSWORD)
    mail.select("INBOX")

    _, msgs = mail.search(None, "ALL")
    ids = msgs[0].split()[-count:]

    result = f"📬 Letzte {count} E-Mails\n{'='*40}\n"
    for i in reversed(ids):
        _, data = mail.fetch(i, "(RFC822)")
        msg = email.message_from_bytes(data[0][1])

        subject = decode_str(msg["Subject"])
        sender  = decode_str(msg["From"])
        date    = msg["Date"]

        result += f"📧 Von:     {sender}\n"
        result += f"   Betreff: {subject}\n"
        result += f"   Datum:   {date}\n"
        result += f"{'─'*40}\n"

    mail.logout()
    return result

@mcp.tool()
def get_email_body(index: int) -> str:
    """Inhalt einer bestimmten E-Mail abrufen (index = Nummer aus get_emails)"""
    mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    mail.login(EMAIL, PASSWORD)
    mail.select("INBOX")

    _, msgs = mail.search(None, "ALL")
    ids = msgs[0].split()
    if index < 1 or index > len(ids):
        return "Ungültiger Index"

    _, data = mail.fetch(ids[-index], "(RFC822)")
    msg = email.message_from_bytes(data[0][1])

    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                break
    else:
        body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

    return f"Betreff: {decode_str(msg['Subject'])}\n\n{body}"

if __name__ == "__main__":
    mcp.run()
