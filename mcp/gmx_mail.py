import imaplib
import email
import os
import sys
from email.header import decode_header
from mcp.server.fastmcp import FastMCP
from profiling import module_load, profile

mcp = FastMCP("email")
module_load("email")

IMAP_HOST = "imap.gmx.net"
IMAP_PORT = 993
EMAIL    = os.environ.get("GMX_EMAIL", "")
PASSWORD = os.environ.get("GMX_PASSWORD", "")

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

def get_emails_impl(count: int = 10, *, imap_factory=None, email_account=None, password=None) -> str:
    """Letzte E-Mails aus dem GMX Posteingang abrufen"""
    imap_factory = imap_factory or (lambda: imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT))
    email_account = email_account or EMAIL
    password = password or PASSWORD

    mail = imap_factory()
    mail.login(email_account, password)
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

def get_email_body_impl(index: int, *, imap_factory=None, email_account=None, password=None) -> str:
    """Inhalt einer bestimmten E-Mail abrufen (index = Nummer aus get_emails)"""
    imap_factory = imap_factory or (lambda: imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT))
    email_account = email_account or EMAIL
    password = password or PASSWORD

    mail = imap_factory()
    mail.login(email_account, password)
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

@mcp.tool()
@profile("email.get_emails")
def get_emails(count: int = 10) -> str:
    """Letzte E-Mails aus dem GMX Posteingang abrufen"""
    return get_emails_impl(count)

@mcp.tool()
@profile("email.get_email_body")
def get_email_body(index: int) -> str:
    """Inhalt einer bestimmten E-Mail abrufen (index = Nummer aus get_emails)"""
    return get_email_body_impl(index)

if __name__ == "__main__":
    if "--test" in sys.argv:
        print("[test] get_emails():")
        print(get_emails_impl())
    else:
        mcp.run()
