"""Tests für mqtt_notify.py — DI + MQTT Publish."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import mqtt_notify


def test_mqtt_notify_send_notification(mocker):
    """send_notification_impl: mqtt_single wird aufgerufen."""
    mock_mqtt_single = mocker.MagicMock()

    result = mqtt_notify.send_notification_impl(
        "Test message",
        topic="test/topic",
        title=None,
        retain=False,
        qos=0,
        mqtt_single=mock_mqtt_single,
        mqtt_host="localhost",
        mqtt_port=1883,
        mqtt_user=None,
        mqtt_password=None,
        default_topic="claude/notifications",
        use_tls=False,
    )

    mock_mqtt_single.assert_called_once()
    call_args = mock_mqtt_single.call_args
    assert call_args.kwargs["topic"] == "test/topic"
    assert call_args.kwargs["payload"] == "Test message"
    assert "Nachricht gesendet" in result


def test_mqtt_notify_send_notification_with_title(mocker):
    """send_notification_impl mit title: JSON payload."""
    mock_mqtt_single = mocker.MagicMock()

    result = mqtt_notify.send_notification_impl(
        "Test message",
        topic="test/topic",
        title="Test Title",
        retain=False,
        qos=0,
        mqtt_single=mock_mqtt_single,
        mqtt_host="localhost",
        mqtt_port=1883,
        mqtt_user=None,
        mqtt_password=None,
        default_topic="claude/notifications",
        use_tls=False,
    )

    mock_mqtt_single.assert_called_once()
    call_args = mock_mqtt_single.call_args
    payload = call_args.kwargs["payload"]
    assert '"title": "Test Title"' in payload
    assert '"message": "Test message"' in payload


def test_mqtt_notify_send_notifications_multi(mocker):
    """send_notifications_multi_impl: mqtt_multiple wird aufgerufen."""
    mock_mqtt_multiple = mocker.MagicMock()

    messages = [
        {"topic": "test/1", "message": "Message 1"},
        {"topic": "test/2", "message": "Message 2", "retain": True},
    ]

    result = mqtt_notify.send_notifications_multi_impl(
        messages,
        mqtt_multiple=mock_mqtt_multiple,
        mqtt_host="localhost",
        mqtt_port=1883,
        mqtt_user=None,
        mqtt_password=None,
        use_tls=False,
    )

    mock_mqtt_multiple.assert_called_once()
    call_args = mock_mqtt_multiple.call_args
    msgs = call_args.args[0]
    assert len(msgs) == 2
    assert msgs[0]["topic"] == "test/1"
    assert msgs[1]["retain"] is True
    assert "2 Nachrichten gesendet" in result
