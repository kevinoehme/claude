"""Tests für mail_check.py — DI + Baseline/UID tracking."""
import sys
from pathlib import Path
from unittest.mock import MagicMock
import email

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import mail_check
import db


def test_mail_check_baseline_first_run(tmp_db, mocker):
    """Erstes Lauf (kein UID in DB): Baseline wird gesetzt."""
    mock_imap_factory = mocker.MagicMock()
    mock_imap = MagicMock()
    mock_imap_factory.return_value = mock_imap

    # Simulate IMAP response with UIDs [1, 2, 3]
    mock_imap.uid.return_value = ("OK", [b"1 2 3"])

    result = mail_check.get_new_emails_impl(
        max_report=10,
        imap_factory=mock_imap_factory,
        db_connect=tmp_db,
        email_account="test@gmx.de",
        password="password",
    )

    assert "Baseline gesetzt" in result
    assert "3" in result  # UID 3 should be in baseline

    # Verify baseline was stored
    with tmp_db() as con:
        last_uid = db.get_last_seen_uid(con, "test@gmx.de")
        assert last_uid == 3


def test_mail_check_no_new_emails(tmp_db, mocker):
    """Keine neuen Mails: "Keine neuen" Nachricht."""
    mock_imap_factory = mocker.MagicMock()
    mock_imap = MagicMock()
    mock_imap_factory.return_value = mock_imap
    mock_imap.uid.return_value = ("OK", [b""])  # No UIDs

    # Set baseline
    with tmp_db() as con:
        db.set_last_seen_uid(con, "test@gmx.de", 3)

    result = mail_check.get_new_emails_impl(
        max_report=10,
        imap_factory=mock_imap_factory,
        db_connect=tmp_db,
        email_account="test@gmx.de",
        password="password",
    )

    assert "Keine neuen" in result


def test_mail_check_new_emails_with_content(tmp_db, mocker):
    """Neue Mails: Headers werden korrekt dekodiert."""
    mock_imap_factory = mocker.MagicMock()
    mock_imap = MagicMock()
    mock_imap_factory.return_value = mock_imap

    # Simulate: UIDs [4, 5] are new (baseline is 3)
    mock_imap.uid.return_value = ("OK", [b"4 5"])

    # Mock header fetch for UID 4
    msg = email.message.EmailMessage()
    msg["From"] = "sender@example.com"
    msg["Subject"] = "Test Subject"
    msg["Date"] = "Wed, 3 Jun 2026 12:00:00 +0000"
    msg_bytes = msg.as_bytes()

    mock_imap.uid.side_effect = [
        ("OK", [b"4 5"]),  # search response
        ("OK", [(None, msg_bytes)]),  # fetch for UID 5
        ("OK", [(None, msg_bytes)]),  # fetch for UID 4
    ]

    # Set baseline
    with tmp_db() as con:
        db.set_last_seen_uid(con, "test@gmx.de", 3)

    result = mail_check.get_new_emails_impl(
        max_report=10,
        imap_factory=mock_imap_factory,
        db_connect=tmp_db,
        email_account="test@gmx.de",
        password="password",
    )

    assert "2 neue E-Mails" in result
    assert "sender@example.com" in result or "example.com" in result
    assert "Test Subject" in result

    # Verify UID was updated
    with tmp_db() as con:
        last_uid = db.get_last_seen_uid(con, "test@gmx.de")
        assert last_uid == 5
