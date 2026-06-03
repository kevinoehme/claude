import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_http_get(mocker):
    """Mock für httpx.get."""
    return mocker.patch("httpx.get")


@pytest.fixture
def tmp_db(tmp_path):
    """Fresh SQLite DB in tmp dir for tests. Returns a db.connect callable."""
    db_path = tmp_path / "test.db"

    # Import db module and override the path
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import db

    original_db_path = db.DB_PATH
    db.DB_PATH = db_path
    db.init_db()

    def mock_connect():
        return db.connect()

    yield mock_connect

    # Restore original
    db.DB_PATH = original_db_path


@pytest.fixture
def mock_imap(mocker):
    """Mock für imaplib.IMAP4_SSL."""
    mock_imap_cls = mocker.patch("imaplib.IMAP4_SSL")
    mock_imap_instance = MagicMock()
    mock_imap_cls.return_value = mock_imap_instance
    return mock_imap_instance


@pytest.fixture
def mock_mqtt_single(mocker):
    """Mock für paho.mqtt.publish.single."""
    return mocker.patch("paho.mqtt.publish.single")


@pytest.fixture
def mock_mqtt_multiple(mocker):
    """Mock für paho.mqtt.publish.multiple."""
    return mocker.patch("paho.mqtt.publish.multiple")
