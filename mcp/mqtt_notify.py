"""MQTT-Notification-MCP für Briefing-/Alert-Workflows.

Generischer Notification-Channel: jedes Tool-/Agent-System kann via
`send_notification` eine Nachricht auf einen MQTT-Topic schicken. Home
Assistant abonniert die Topics und routet z.B. Briefings an einen
Alexa-Echo-Dot oder triggert andere Automationen.

Konfiguration via Env-Vars:
- MQTT_HOST           (Pflicht)
- MQTT_PORT           (Default 1883)
- MQTT_USER           (optional)
- MQTT_PASSWORD       (optional)
- MQTT_DEFAULT_TOPIC  (optional, Default "claude/notifications")
- MQTT_TLS            (optional, "1"/"true" → TLS auf Default-Port 8883)
"""

import json
import os
import ssl
import sys

import paho.mqtt.publish as publish

from mcp.server.fastmcp import FastMCP

from profiling import module_load, profile

mcp = FastMCP("mqtt_notify")
module_load("mqtt_notify")

MQTT_HOST = os.environ.get("MQTT_HOST", "")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")
DEFAULT_TOPIC = os.environ.get("MQTT_DEFAULT_TOPIC", "claude/notifications")
USE_TLS = os.environ.get("MQTT_TLS", "").lower() in ("1", "true", "yes")


def _auth():
    if MQTT_USER:
        return {"username": MQTT_USER, "password": MQTT_PASSWORD or ""}
    return None


def _tls():
    if USE_TLS:
        return {"tls_version": ssl.PROTOCOL_TLS_CLIENT}
    return None


def send_notification_impl(
    message: str,
    topic: str | None = None,
    title: str | None = None,
    retain: bool = False,
    qos: int = 0,
    *,
    mqtt_single=None,
    mqtt_host=None,
    mqtt_port=None,
    mqtt_user=None,
    mqtt_password=None,
    default_topic=None,
    use_tls=None,
) -> str:
    """Sendet eine Nachricht auf einen MQTT-Topic."""
    mqtt_single = mqtt_single or publish.single
    mqtt_host = mqtt_host or MQTT_HOST
    mqtt_port = mqtt_port or MQTT_PORT
    mqtt_user = mqtt_user or MQTT_USER
    mqtt_password = mqtt_password or MQTT_PASSWORD
    default_topic = default_topic or DEFAULT_TOPIC
    use_tls = use_tls if use_tls is not None else USE_TLS

    target_topic = topic or default_topic
    if title:
        payload = json.dumps({"title": title, "message": message}, ensure_ascii=False)
    else:
        payload = message

    auth = None
    if mqtt_user:
        auth = {"username": mqtt_user, "password": mqtt_password or ""}
    tls = None
    if use_tls:
        tls = {"tls_version": ssl.PROTOCOL_TLS_CLIENT}

    mqtt_single(
        topic=target_topic,
        payload=payload,
        qos=qos,
        retain=retain,
        hostname=mqtt_host,
        port=mqtt_port,
        auth=auth,
        tls=tls,
        client_id="claude-mqtt-notify",
        keepalive=10,
    )
    return f"📌 Nachricht gesendet → {target_topic} ({len(payload)} Bytes)"


def send_notifications_multi_impl(messages: list[dict], *, mqtt_multiple=None, mqtt_host=None, mqtt_port=None, mqtt_user=None, mqtt_password=None, use_tls=None) -> str:
    """Sendet mehrere MQTT-Nachrichten in einem TCP-Connect."""
    mqtt_multiple = mqtt_multiple or publish.multiple
    mqtt_host = mqtt_host or MQTT_HOST
    mqtt_port = mqtt_port or MQTT_PORT
    mqtt_user = mqtt_user or MQTT_USER
    mqtt_password = mqtt_password or MQTT_PASSWORD
    use_tls = use_tls if use_tls is not None else USE_TLS

    if not messages:
        return "⚠️ Keine Nachrichten übergeben."

    msgs = []
    for i, m in enumerate(messages):
        topic = m.get("topic")
        text = m.get("message")
        if not topic or text is None:
            return f"FEHLER: Element {i} braucht 'topic' und 'message': {m!r}"
        title = m.get("title")
        if title:
            payload = json.dumps({"title": title, "message": text}, ensure_ascii=False)
        else:
            payload = text
        msgs.append({
            "topic": topic,
            "payload": payload,
            "qos": int(m.get("qos", 0)),
            "retain": bool(m.get("retain", False)),
        })

    auth = None
    if mqtt_user:
        auth = {"username": mqtt_user, "password": mqtt_password or ""}
    tls = None
    if use_tls:
        tls = {"tls_version": ssl.PROTOCOL_TLS_CLIENT}

    mqtt_multiple(
        msgs,
        hostname=mqtt_host,
        port=mqtt_port,
        auth=auth,
        tls=tls,
        client_id="claude-mqtt-notify",
        keepalive=10,
    )
    topics_str = ", ".join(m["topic"] for m in msgs)
    return f"📌 {len(msgs)} Nachrichten gesendet (1 TCP-Connect) → {topics_str}"


@mcp.tool()
@profile("mqtt_notify.send_notification")
def send_notification(
    message: str,
    topic: str | None = None,
    title: str | None = None,
    retain: bool = False,
    qos: int = 0,
) -> str:
    """Sendet eine Nachricht auf einen MQTT-Topic."""
    return send_notification_impl(message, topic, title, retain, qos)


@mcp.tool()
@profile("mqtt_notify.send_notifications_multi")
def send_notifications_multi(messages: list[dict]) -> str:
    """Sendet mehrere MQTT-Nachrichten in einem TCP-Connect."""
    return send_notifications_multi_impl(messages)


if __name__ == "__main__":
    if "--test" in sys.argv:
        print("[test] send_notification_impl():")
        print(send_notification_impl("Test message", topic="test/topic"))
    else:
        mcp.run()
