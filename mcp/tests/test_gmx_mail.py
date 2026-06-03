"""Tests für gmx_mail.py — DI + Header Decoding."""
import sys
from pathlib import Path
from unittest.mock import MagicMock
import email
from email.header import Header

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import gmx_mail


def test_gmx_mail_get_emails_format(mocker):
    """get_emails_impl mit Mock-IMAP: Format korrekt."""
    mock_imap_factory = mocker.MagicMock()
    mock_imap = MagicMock()
    mock_imap_factory.return_value = mock_imap

    # Setup mock IMAP responses
    mock_imap.search.return_value = ("OK", [b"1 2"])

    msg = email.message.EmailMessage()
    msg["From"] = "test@example.com"
    msg["Subject"] = "Test Subject"
    msg["Date"] = "Wed, 3 Jun 2026 12:00:00 +0000"
    msg_bytes = msg.as_bytes()

    mock_imap.fetch.side_effect = [
        ("OK", [(None, msg_bytes)]),  # for ID 2
        ("OK", [(None, msg_bytes)]),  # for ID 1
    ]

    result = gmx_mail.get_emails_impl(
        count=2,
        imap_factory=mock_imap_factory,
        email_account="user@gmx.de",
        password="password",
    )

    assert "📬 Letzte 2 E-Mails" in result
    assert "test@example.com" in result
    assert "Test Subject" in result
    mock_imap.logout.assert_called_once()


def test_gmx_mail_decode_str_utf8():
    """decode_str() mit UTF-8 Subject."""
    # Normal ASCII
    result = gmx_mail.decode_str("Normal Subject")
    assert result == "Normal Subject"

    # MIME encoded
    encoded = Header("Tëst Sübjëct", "utf-8").encode()
    result = gmx_mail.decode_str(encoded)
    assert "Sübjëct" in result or "Test" in result

    # None
    result = gmx_mail.decode_str(None)
    assert result == ""
